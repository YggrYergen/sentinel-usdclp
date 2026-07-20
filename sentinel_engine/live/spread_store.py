r"""sentinel_engine/live/spread_store.py -- persistent ALL-TIME running-MINIMUM
XAUUSD spread store + append-only samples log (GL-T2).

WHY
---
XAUUSD demo spread is currently FIXED at 0.60 USD/oz, but no historical
tick/spread series exists (`LOG_TICKS=False`). Rather than hard-code a static
`--max-spread-open 0.70` gate (GL-T1), we LEARN the thin-market floor online:
every observed spread is recorded and the ALL-TIME running minimum is ratcheted
down whenever a strictly-smaller spread is seen. The adaptive OPEN-gate then
admits an OPEN only when the current spread is within `eps` of that learned
running-min (`current <= running_min + eps`), so entries fire in the thinnest
regime the account has ever shown and PAUSE whenever spread widens.

STATE (JSON, atomically written)
--------------------------------
    {
      "running_min": 0.60,          # all-time minimum spread seen (USD/oz)
      "running_min_ts": "<iso>",    # when that minimum was observed
      "sample_count": 12345,        # total samples recorded
      "last_spread": 0.60,          # most recent spread recorded
      "last_ts": "<iso>",           # most recent record ts
      "created_ts": "<iso>",        # first-ever record ts
      "symbol": "XAUUSD"
    }

Persisted at a FIXED, gitignored data path (``data/xauusd_spread_store.json``)
so it survives restarts but is never committed (it is runtime state, machine-
local). Writes are ATOMIC (temp file in the same dir + ``os.replace``) so a
crash mid-write can never corrupt the store -- a reader always sees either the
old complete file or the new complete file, never a torn one.

SAMPLES LOG (append-only CSV: ``data/xauusd_spread_samples.csv``)
----------------------------------------------------------------
Every ``record()`` appends one ``ts,spread`` row (header written once). This is
the raw series for later re-calibration; it is append-only and never rewritten.

HANDOFF SAFETY
--------------
This store is designed for a "standalone capture now, armed executor takes over
later" handoff. Both writers use atomic replace, so a reader is always safe.
HOWEVER two PROCESSES writing the SAME store file concurrently can still race
(last-writer-wins on the JSON; a ratchet from one could be lost). Therefore:

    DO NOT run the standalone `--capture-spread` capturer and an ARMED executor
    that writes the same store at the same instant. Run ONE writer at a time.
    (Handoff = stop the capturer, then start the executor -- both read the same
    persisted running-min, so no learning is lost across the switch.)

Read-only: this module NEVER places an order. It only records observed spreads.
"""
from __future__ import annotations

import csv
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STORE_NAME = "xauusd_spread_store.json"
DEFAULT_SAMPLES_NAME = "xauusd_spread_samples.csv"

DEFAULT_SYMBOL = "XAUUSD"

# Sentinel meaning "use the default data path, resolved lazily at construction
# so a SPREAD_STORE_DIR env override (tests only) is honoured post-import".
_USE_DEFAULT = object()


def _default_store_dir() -> Path:
    """FIXED, gitignored (data/ is in .gitignore) runtime-state dir. An optional
    SPREAD_STORE_DIR env override redirects BOTH files (used by tests to avoid
    writing into the real data/ dir; never needed in production)."""
    env = os.environ.get("SPREAD_STORE_DIR")
    return Path(env) if env else REPO_ROOT / "data"


# Back-compat module constants (resolved at import; the class resolves lazily).
DEFAULT_STORE_PATH = _default_store_dir() / DEFAULT_STORE_NAME
DEFAULT_SAMPLES_PATH = _default_store_dir() / DEFAULT_SAMPLES_NAME

TsLike = Union[datetime, int, float, str, None]

_SAMPLES_HEADER = ["ts", "spread"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ts(ts: TsLike) -> str:
    """Return an ISO-8601 string for any accepted ts form."""
    if ts is None:
        return _now_iso()
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        return ts.isoformat()
    # int/float -> unix seconds (UTC).
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


class SpreadStore:
    """Persistent all-time running-minimum spread store + samples log.

    All writes are atomic. `load()` on construction (or explicitly) restores the
    running-min from disk so learning survives restarts.
    """

    def __init__(self, store_path: Any = _USE_DEFAULT,
                 samples_path: Any = _USE_DEFAULT,
                 symbol: str = DEFAULT_SYMBOL, *, log_samples: bool = True):
        # Resolve the default paths LAZILY (honours SPREAD_STORE_DIR post-import).
        if store_path is _USE_DEFAULT:
            store_path = _default_store_dir() / DEFAULT_STORE_NAME
        if samples_path is _USE_DEFAULT:
            samples_path = _default_store_dir() / DEFAULT_SAMPLES_NAME
        self.store_path = Path(store_path)
        self.samples_path = Path(samples_path) if samples_path is not None else None
        self.symbol = symbol
        self.log_samples = log_samples and self.samples_path is not None

        self.running_min: float | None = None
        self.running_min_ts: str | None = None
        self.sample_count: int = 0
        self.last_spread: float | None = None
        self.last_ts: str | None = None
        self.created_ts: str | None = None

        self.load()

    # -- persistence ------------------------------------------------------
    def load(self) -> "SpreadStore":
        """Restore state from disk if the store file exists (else start empty).
        A corrupt/unreadable file is treated as empty (defensive: never crash a
        capturer on a bad read; the next `record` re-establishes a clean store).
        """
        if not self.store_path.exists():
            return self
        try:
            with self.store_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return self
        rm = data.get("running_min")
        self.running_min = float(rm) if rm is not None else None
        self.running_min_ts = data.get("running_min_ts")
        self.sample_count = int(data.get("sample_count", 0) or 0)
        ls = data.get("last_spread")
        self.last_spread = float(ls) if ls is not None else None
        self.last_ts = data.get("last_ts")
        self.created_ts = data.get("created_ts")
        return self

    def _state_dict(self) -> dict[str, Any]:
        return {
            "running_min": self.running_min,
            "running_min_ts": self.running_min_ts,
            "sample_count": self.sample_count,
            "last_spread": self.last_spread,
            "last_ts": self.last_ts,
            "created_ts": self.created_ts,
            "symbol": self.symbol,
        }

    def _persist(self) -> None:
        """Atomically write the JSON state: write a temp file in the SAME
        directory, fsync it, then os.replace() over the target. os.replace is
        atomic on both POSIX and Windows for same-filesystem paths, so a reader
        (or a crash) can only ever see the old or the new complete file."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._state_dict(), indent=2, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.store_path.parent),
            prefix=self.store_path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.store_path)
        except BaseException:
            # leave the ORIGINAL store intact; clean up the temp turd.
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _append_sample(self, ts_iso: str, spread: float) -> None:
        if not self.log_samples or self.samples_path is None:
            return
        self.samples_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.samples_path.exists()
        with self.samples_path.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(_SAMPLES_HEADER)
            w.writerow([ts_iso, f"{spread:.6f}"])

    # -- API --------------------------------------------------------------
    def record(self, spread: float, ts: TsLike = None) -> float | None:
        """Record ONE observed spread. ALWAYS appends the sample and updates
        last_spread/last_ts/sample_count; RATCHETS running_min DOWN only when
        `spread` is STRICTLY smaller than the current running_min. Persists the
        JSON state atomically and appends to the samples log. Ignores non-finite
        or negative spreads (bad tick) -- returns the current running_min
        unchanged without recording. Returns the (possibly updated)
        running_min.
        """
        if spread is None or not math.isfinite(spread) or spread < 0:
            return self.running_min
        spread = float(spread)
        ts_iso = _normalize_ts(ts)

        if self.created_ts is None:
            self.created_ts = ts_iso
        self.last_spread = spread
        self.last_ts = ts_iso
        self.sample_count += 1

        # RATCHET: only a STRICTLY-smaller spread lowers the all-time minimum.
        if self.running_min is None or spread < self.running_min:
            self.running_min = spread
            self.running_min_ts = ts_iso

        self._append_sample(ts_iso, spread)
        self._persist()
        return self.running_min

    def threshold(self, eps: float = 0.0) -> float | None:
        """Adaptive OPEN-gate threshold = running_min + eps, or None if no
        sample has ever been recorded (caller must then NOT adaptively gate)."""
        if self.running_min is None:
            return None
        return self.running_min + eps

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (f"SpreadStore(symbol={self.symbol!r}, running_min={self.running_min}, "
                f"sample_count={self.sample_count}, last_spread={self.last_spread})")
