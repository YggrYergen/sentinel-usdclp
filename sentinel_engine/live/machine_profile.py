"""sentinel_engine.live.machine_profile -- per-machine configuration for the
live executor stack (SENTINEL, 2026-07-15). NOT a safety module: this is
mutable, machine-local SELECTION config. It can only pick one login out of
the hard-coded `guard_cuenta.SANCTIONED_DEMO_LOGINS` frozenset -- it can
NEVER extend that set. See `sentinel_engine.live.guard_cuenta` module
docstring for the safety principle this module must respect.

WHY THIS EXISTS: two machines share this branch (`alvaro`) and each has its
own MT5 install layout and demo login:
  - Machine 1 (THIS repo's original values): portable install
    `D:\\FOREX\\MT5_Portable\\terminal64.exe`, `portable=True`,
    login 2883015767.
  - Machine "TOMACHINE": standard (non-portable) install
    `C:\\Program Files\\Capitaria MT5 Terminal\\terminal64.exe`,
    `portable=False`, login 2883016567.
Both machines run the SAME tracked source files. Instead of each machine
hardcoding its own values into shared files (which silently breaks the other
machine on merge -- see the 2026-07-15 incident this module fixes), every
call site reads `load_profile()` here.

CONFIG SOURCE: optional JSON file at `scripts/live/machine_local.json`
(gitignored -- see `.gitignore` and `scripts/live/machine_local.example.json`
for the tracked template documenting both machines' blocks). If the file is
ABSENT, this module defaults to Machine 1's values -- zero-config backward
compatibility for the machine this repo originated on.

Keys (all optional except where noted):
  terminal_path   (str)  -- full path to terminal64.exe
  portable        (bool) -- passed as `mt5.initialize(..., portable=...)`
  demo_login      (int)  -- MUST be a member of
                            `guard_cuenta.SANCTIONED_DEMO_LOGINS`
  terminal_marker (str)  -- lower-cased path fragment used for process-list
                            matching (`preflight_live.portable_running`,
                            `run_live_20._portable_running`, etc). If absent,
                            derived from `terminal_path` (parent directory
                            name, lower-cased -- e.g.
                            "C:\\Program Files\\Capitaria MT5 Terminal\\terminal64.exe"
                            -> "capitaria mt5 terminal").
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINE_LOCAL_JSON = REPO_ROOT / "scripts" / "live" / "machine_local.json"

# Machine 1 defaults -- zero-config backward compatibility when
# machine_local.json is absent (this is the machine the repo originated on).
DEFAULT_TERMINAL_PATH = r"D:\FOREX\MT5_Portable\terminal64.exe"
DEFAULT_PORTABLE = True
DEFAULT_DEMO_LOGIN = 2883015767
DEFAULT_TERMINAL_MARKER = "mt5_portable"


class MachineProfileError(RuntimeError):
    """Raised when machine_local.json is present but invalid (e.g. its
    demo_login is not in the hard-coded sanctioned set)."""


@dataclass(frozen=True)
class MachineProfile:
    terminal_path: Path
    portable: bool
    demo_login: int
    terminal_marker: str


def _derive_marker(terminal_path: str) -> str:
    """Best-effort default marker: the lower-cased parent directory name of
    the terminal exe (e.g. '...\\Capitaria MT5 Terminal\\terminal64.exe' ->
    'capitaria mt5 terminal'; '...\\MT5_Portable\\terminal64.exe' ->
    'mt5_portable')."""
    return Path(terminal_path).parent.name.lower()


def _validate_demo_login(demo_login: int) -> None:
    # Imported lazily to avoid a hard import-time cycle with guard_cuenta
    # (guard_cuenta.DEMO_LOGIN resolves via this module's load_profile()).
    from sentinel_engine.live.guard_cuenta import SANCTIONED_DEMO_LOGINS
    if demo_login not in SANCTIONED_DEMO_LOGINS:
        raise MachineProfileError(
            f"machine_local.json demo_login={demo_login} is NOT a member of "
            f"the hard-coded SANCTIONED_DEMO_LOGINS set "
            f"{sorted(SANCTIONED_DEMO_LOGINS)} (sentinel_engine.live."
            "guard_cuenta). Fix machine_local.json -- config can only SELECT "
            "a sanctioned login, never introduce a new one.")


def load_profile(*, path: Path | None = None) -> MachineProfile:
    """Load the machine profile. Returns Machine 1 defaults if `path` (default
    `scripts/live/machine_local.json`) does not exist. Raises
    `MachineProfileError` loudly if the file exists but is invalid JSON, is
    missing required keys, or names an unsanctioned `demo_login`."""
    json_path = MACHINE_LOCAL_JSON if path is None else path

    if not json_path.exists():
        return MachineProfile(
            terminal_path=Path(DEFAULT_TERMINAL_PATH),
            portable=DEFAULT_PORTABLE,
            demo_login=DEFAULT_DEMO_LOGIN,
            terminal_marker=DEFAULT_TERMINAL_MARKER,
        )

    try:
        raw: dict[str, Any] = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MachineProfileError(
            f"failed to read/parse {json_path}: {exc!r}") from exc

    try:
        terminal_path = str(raw["terminal_path"])
        portable = bool(raw["portable"])
        demo_login = int(raw["demo_login"])
    except KeyError as exc:
        raise MachineProfileError(
            f"{json_path} is missing required key {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise MachineProfileError(
            f"{json_path} has a malformed value: {exc!r}") from exc

    _validate_demo_login(demo_login)

    terminal_marker = str(raw.get("terminal_marker") or _derive_marker(terminal_path))

    return MachineProfile(
        terminal_path=Path(terminal_path),
        portable=portable,
        demo_login=demo_login,
        terminal_marker=terminal_marker.lower(),
    )
