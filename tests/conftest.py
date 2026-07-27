"""tests/conftest.py -- session-wide test isolation from MACHINE-LOCAL
DEPLOYMENT STATE (added 2026-07-27).

WHY: `scripts/live/machine_local.json` is a GITIGNORED, per-machine deployment
file that the operator edits by hand when the MT5 terminal's account changes.
Several order-capable modules resolve it at IMPORT time
(`preflight_live._PROFILE = load_profile()`, `guard_cuenta.DEMO_LOGIN =
_resolve_demo_login()`, ...), so with it present the test suite's outcome
depended on whatever that untracked file happened to contain on the machine
running pytest. Concretely, on 2026-07-27 the sanctioned set was rotated
(2883016567 retired, 2883016902 sanctioned) and every module importing
`preflight_live` failed COLLECTION with `MachineProfileError` on the deploying
machine until the operator got around to updating the JSON -- a tracked-code
test run broken by untracked local state.

WHAT: point `machine_profile.MACHINE_LOCAL_JSON` at a path that does not exist,
for the whole session, BEFORE any test module (and therefore any production
module) is imported. `load_profile()` then returns the Machine 1 zero-config
DEFAULTS, which is exactly what a clean checkout / CI / Machine 1 already saw.

WHAT THIS DOES *NOT* DO: it does not weaken any check. The guard's hard-coded
`SANCTIONED_DEMO_LOGINS` frozenset, `assert_demo` and
`machine_profile._validate_demo_login` are untouched and still run in full --
`tests/live/test_machine_profile.py` keeps exercising the real validation
against explicit `tmp_path` files, including the rejection of unsanctioned and
RETIRED logins. Only the DEFAULT lookup path is redirected, and only in tests.
Verifying the live machine's actual `machine_local.json` is deployment's job
(preflight + the watchdog account probe), not the unit suite's.
"""
from __future__ import annotations

from pathlib import Path

from sentinel_engine.live import machine_profile as _mp

# Deliberately inside the repo tree but non-existent, so `load_profile()` takes
# its "file absent -> Machine 1 defaults" branch. Never created by the suite.
_mp.MACHINE_LOCAL_JSON = (
    Path(_mp.REPO_ROOT) / "scripts" / "live" / "machine_local.__pytest_absent__.json"
)
assert not _mp.MACHINE_LOCAL_JSON.exists(), (
    "tests/conftest.py expects this sentinel path to NOT exist; delete "
    f"{_mp.MACHINE_LOCAL_JSON} -- the suite must not read a real machine profile"
)
