"""
sentinel_engine.opt.registry — SQLite + Parquet trial registry, and the
deflated Sharpe ratio (Bailey & Lopez de Prado) used to report an honest
p-value for a study's winner once the number of trials tried is accounted
for.

Design source: docs/superpowers/plans/2026-07-07-sentinel-revamp.md Phase 4
task 4.6, and FABLE5_RESPONSE_SENTINEL_REVAMP.md sec 2.6 ("Deflated Sharpe /
trial accounting: the registry records total trials per study; DSR computed
for the winner; the report shows the p-value honestly") and sec 2.10
("Registry: one SQLite DB + Parquet artifacts ... metrics(run_id, metric,
value) -- long format").

Scope (per the locked task): a self-contained trial registry -- every trial
(params + full metric set) persisted to SQLite, per-study trial counts
available for DSR deflation, and large per-trial arrays (e.g. equity curves)
persisted to Parquet via pyarrow, addressable from the SQLite row and
round-trippable. The full studies/variants/runs/metrics schema sketched in
sec 2.10 is reporting-layer scope (task 4.7); this module implements the
trial-level primitive it will be built on.

Windows-safe: pathlib only, explicit utf-8, stdlib sqlite3 + pyarrow, no
OS-version APIs.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.stats import norm, kurtosis as _kurtosis, skew as _skew

_EULER_MASCHERONI = 0.5772156649015329

_SCHEMA = """
CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    created TEXT NOT NULL,
    seed INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id TEXT NOT NULL,
    trial_index INTEGER NOT NULL,
    created TEXT NOT NULL,
    params_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    array_path TEXT,
    FOREIGN KEY (study_id) REFERENCES studies (study_id)
);

CREATE INDEX IF NOT EXISTS idx_trials_study ON trials (study_id);
"""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(payload: Mapping[str, Any]) -> str:
    # sort_keys -> stable/reproducible serialization (determinism guarantee
    # shared with the rest of the P1 core: same input, byte-identical row).
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class TrialRecord:
    """A single round-tripped trial as read back from the registry."""

    study_id: str
    trial_id: int
    trial_index: int
    created: str
    params: dict[str, Any]
    metrics: dict[str, Any]
    arrays: dict[str, list[float]] = field(default_factory=dict)


class TrialRegistry:
    """SQLite (params/metrics/counts) + Parquet (large per-trial arrays)
    registry for optimizer trials.

    Every recorded trial is addressable by (study_id, trial_id); large
    per-trial arrays (equity curves, R-multiple series, ...) are written to
    one Parquet file per trial under `parquet_dir` and referenced from the
    SQLite row so both stores round-trip together.
    """

    def __init__(self, db_path: Path | str, parquet_dir: Path | str) -> None:
        self.db_path = Path(db_path)
        self.parquet_dir = Path(parquet_dir)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "TrialRegistry":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- studies ----------------------------------------------------------

    def ensure_study(
        self,
        study_id: str,
        *,
        seed: int | None = None,
        notes: str | None = None,
    ) -> None:
        """Register a study row if it does not already exist (idempotent)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO studies (study_id, created, seed, notes) "
            "VALUES (?, ?, ?, ?)",
            (study_id, _utcnow_iso(), seed, notes),
        )
        self._conn.commit()

    # -- trials -------------------------------------------------------------

    def record_trial(
        self,
        study_id: str,
        params: Mapping[str, Any],
        metrics: Mapping[str, Any],
        arrays: Mapping[str, Sequence[float]] | None = None,
    ) -> int:
        """Persist one trial. Returns the assigned `trial_id`.

        `params` and `metrics` must be JSON-serializable (the full metric
        set per Fable sec 2.4: pnl_R, PF, winrate, maxDD_R, sharpe, n_trades,
        label_acc, ... -- whatever the caller computed for this trial).
        `arrays` holds large per-trial series (e.g. an equity curve) that
        would bloat the SQLite row; each entry becomes one column (a single
        list-valued row, so entries may differ in length) in a per-trial
        Parquet file.
        """
        trial_index = self.trial_count(study_id)
        created = _utcnow_iso()
        array_path: str | None = None

        conn = self._conn
        cur = conn.execute(
            "INSERT INTO trials (study_id, trial_index, created, params_json, "
            "metrics_json, array_path) VALUES (?, ?, ?, ?, ?, ?)",
            (
                study_id,
                trial_index,
                created,
                _json_dumps(dict(params)),
                _json_dumps(dict(metrics)),
                None,
            ),
        )
        trial_id = int(cur.lastrowid)

        if arrays:
            array_path = self._write_arrays(study_id, trial_id, arrays)
            conn.execute(
                "UPDATE trials SET array_path = ? WHERE trial_id = ?",
                (array_path, trial_id),
            )

        conn.commit()
        return trial_id

    def _write_arrays(
        self,
        study_id: str,
        trial_id: int,
        arrays: Mapping[str, Sequence[float]],
    ) -> str:
        # One row, one list-typed column per array -- tolerates arrays of
        # differing lengths within the same trial and round-trips exact
        # float64 values via Parquet (no precision loss, unlike a naive
        # fixed-width table).
        table = pa.table(
            {name: pa.array([list(map(float, values))]) for name, values in arrays.items()}
        )
        filename = f"{study_id}_{trial_id}.parquet"
        path = self.parquet_dir / filename
        pq.write_table(table, path)
        return filename

    def _read_arrays(self, array_path: str) -> dict[str, list[float]]:
        table = pq.read_table(self.parquet_dir / array_path)
        row = table.to_pylist()[0]
        return {name: list(values) for name, values in row.items()}

    def get_trial(self, study_id: str, trial_id: int) -> TrialRecord:
        row = self._conn.execute(
            "SELECT trial_id, trial_index, created, params_json, metrics_json, "
            "array_path FROM trials WHERE study_id = ? AND trial_id = ?",
            (study_id, trial_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"no trial {trial_id!r} for study {study_id!r}")
        return self._row_to_record(study_id, row)

    def get_all_trials(self, study_id: str) -> list[TrialRecord]:
        rows = self._conn.execute(
            "SELECT trial_id, trial_index, created, params_json, metrics_json, "
            "array_path FROM trials WHERE study_id = ? ORDER BY trial_index ASC",
            (study_id,),
        ).fetchall()
        return [self._row_to_record(study_id, row) for row in rows]

    def _row_to_record(self, study_id: str, row: tuple[Any, ...]) -> TrialRecord:
        trial_id, trial_index, created, params_json, metrics_json, array_path = row
        arrays = self._read_arrays(array_path) if array_path else {}
        return TrialRecord(
            study_id=study_id,
            trial_id=trial_id,
            trial_index=trial_index,
            created=created,
            params=json.loads(params_json),
            metrics=json.loads(metrics_json),
            arrays=arrays,
        )

    def trial_count(self, study_id: str) -> int:
        """Total number of trials persisted for `study_id` so far.

        This is exactly the "N trials tried" the deflated Sharpe ratio
        needs to penalize the winner honestly (Fable sec 2.6/2.10).
        """
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM trials WHERE study_id = ?", (study_id,)
        ).fetchone()
        return int(count)


# --------------------------------------------------------------------------
# Deflated Sharpe ratio (Bailey & Lopez de Prado, 2014).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeflatedSharpeResult:
    """Output of `deflated_sharpe_ratio`.

    `dsr` is P(true Sharpe > 0 | observed Sharpe, N trials) after deflating
    for the number of trials searched and for the non-Normality of the
    return series; `p_value = 1 - dsr` is the honest p-value the report
    (task 4.7) surfaces for the study's winner.
    """

    sharpe: float
    n_trials: int
    expected_max_sharpe_null: float
    dsr: float
    p_value: float


def deflated_sharpe_ratio(
    returns: Sequence[float],
    n_trials: int,
    *,
    trial_sharpe_std: float | None = None,
) -> DeflatedSharpeResult:
    """Deflated Sharpe ratio for a winning trial's return series, penalized
    by the number of trials (`n_trials`) tried to find it.

    Parameters
    ----------
    returns:
        The winner's per-period return series (e.g. per-fold or per-day
        R-multiples). Used to compute the observed (non-deflated) Sharpe
        ratio and its skewness/kurtosis-adjusted standard error.
    n_trials:
        Total number of trials searched in the study (from
        `TrialRegistry.trial_count`). Must be >= 2 -- deflation is undefined
        for a single, untried trial.
    trial_sharpe_std:
        Standard deviation of the Sharpe ratios observed *across all trials*
        in the study (i.e. `np.std([t.metrics["sharpe"] for t in trials])`).
        This is the "V[SR_n]" term of Bailey-Lopez de Prado: the spread of
        skill across the trials searched, used to estimate the expected
        maximum Sharpe achievable by pure luck with `n_trials` independent
        attempts. When the caller has not yet computed it (e.g. a study
        with only one trial so far), it defaults to 1.0 -- a deliberately
        conservative (variance-preserving) placeholder; callers with a real
        trial population should always pass the empirical value.

    Returns
    -------
    DeflatedSharpeResult with the observed Sharpe, the trial count, the
    expected maximum Sharpe achievable under the null of skill-less search
    (`expected_max_sharpe_null`, "SR0"), the deflated Sharpe ratio (a
    probability in [0, 1]) and its complement, the honest p-value.
    """
    if n_trials < 2:
        raise ValueError("deflated_sharpe_ratio requires n_trials >= 2")

    values = np.asarray(list(returns), dtype=float)
    n_obs = values.size
    if n_obs < 2:
        raise ValueError("deflated_sharpe_ratio requires at least 2 return observations")

    std = values.std(ddof=1)
    if std == 0.0:
        raise ValueError("returns have zero variance; Sharpe ratio undefined")

    sharpe_hat = float(values.mean() / std)
    gamma3 = float(_skew(values, bias=False))
    # scipy's kurtosis(..., fisher=False) already returns the non-excess
    # (normal == 3) convention Bailey-Lopez de Prado's formula expects.
    gamma4 = float(_kurtosis(values, fisher=False, bias=False))

    variance_sr = 1.0 if trial_sharpe_std is None else float(trial_sharpe_std) ** 2
    if variance_sr <= 0.0:
        variance_sr = 1.0

    # Expected maximum Sharpe ratio ("SR0") of `n_trials` independent,
    # skill-less (zero true Sharpe) attempts -- Bailey & Lopez de Prado
    # (2014), eq. for E[max SR_n].
    sr0 = math.sqrt(variance_sr) * (
        (1 - _EULER_MASCHERONI) * norm.ppf(1 - 1.0 / n_trials)
        + _EULER_MASCHERONI * norm.ppf(1 - 1.0 / (n_trials * math.e))
    )

    sigma_sr = math.sqrt(
        max(
            (1 - gamma3 * sharpe_hat + ((gamma4 - 1) / 4.0) * sharpe_hat**2)
            / (n_obs - 1),
            1e-12,
        )
    )

    dsr = float(norm.cdf((sharpe_hat - sr0) / sigma_sr))
    p_value = 1.0 - dsr

    return DeflatedSharpeResult(
        sharpe=sharpe_hat,
        n_trials=int(n_trials),
        expected_max_sharpe_null=float(sr0),
        dsr=dsr,
        p_value=p_value,
    )


# --------------------------------------------------------------------------
# P63 (Wave 6 governance): the "too-good-to-be-true" trigger, made STRUCTURAL.
# --------------------------------------------------------------------------

# Multiplier on the DSR's skill-less null-max ("SR0", `expected_max_sharpe_null`)
# above which a run is deemed too-good-to-be-true and must be audited. Set to
# 1.0: a config whose HONEST observed Sharpe merely reaches the level that pure
# luck across ALL the trials searched would be EXPECTED to produce is already
# implausible on its own merits -- it clears the same luck-bar the DSR uses to
# deflate the winner, so flagging at that boundary keeps the governance trigger
# internally consistent with the honest reference. Named constant (not a magic
# literal) so the plausibility bound is documented and tunable in one place.
AUDIT_REQUIRED_NULL_MAX_MULT = 1.0


def too_good_to_be_true(
    sharpe: float,
    n_trials: int,
    *,
    trial_sharpe_std: float | None = None,
    null_max_mult: float = AUDIT_REQUIRED_NULL_MAX_MULT,
) -> bool:
    """Pure, side-effect-free "too-good-to-be-true" verdict for one run's
    honest Sharpe, keyed off the SAME skill-less null-max luck-bar the
    deflated Sharpe ratio uses (`expected_max_sharpe_null`, "SR0").

    Returns True iff ``sharpe >= null_max_mult * SR0``, where SR0 is the
    expected maximum Sharpe achievable by pure luck with `n_trials`
    independent skill-less attempts (Bailey & Lopez de Prado). Reusing that
    exact null keeps the governance trigger internally consistent with the
    honest DSR reference: a config at/above the luck-bar is implausibly good
    and must be audited.

    This is GOVERNANCE ONLY -- a read-only threshold test. It computes SR0 the
    same way `deflated_sharpe_ratio` does and NEVER mutates any score/DSR.
    Deterministic: same inputs -> same verdict.
    """
    variance_sr = 1.0 if trial_sharpe_std is None else float(trial_sharpe_std) ** 2
    if variance_sr <= 0.0:
        variance_sr = 1.0
    if int(n_trials) < 2:
        # SR0 is undefined for a single untried attempt -- with no trial
        # search there is no luck-bar to clear, so nothing is "too good".
        return False

    sr0 = math.sqrt(variance_sr) * (
        (1 - _EULER_MASCHERONI) * norm.ppf(1 - 1.0 / n_trials)
        + _EULER_MASCHERONI * norm.ppf(1 - 1.0 / (n_trials * math.e))
    )
    return float(sharpe) >= float(null_max_mult) * float(sr0)
