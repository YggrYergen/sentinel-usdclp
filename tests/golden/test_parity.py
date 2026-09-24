"""
Task 0.2 / P1 Task 1.6b: Parity test — the baseline lock.

For each of the 3 target instruments (usdclp, gold, nasdaq), this test runs
the headless `sentinel_engine.engine.Engine` (via `capture_engine`, driven by
a deterministic `FakeFeed`) and asserts the result is recursively equal to
the committed golden JSON in `fixtures/<instrument>.json`. The parity gate
was repointed from the legacy scoring path (`capture_golden`, still proven
equivalent — see `tests/test_engine.py`) to the new Engine as of Task 1.6b;
the golden fixtures were regenerated from the Engine at the same time.

This test must stay GREEN after every future scoring-touching refactor. If
it goes red, that means observable output changed — either a genuine
regression to fix, or an intentional change that requires regenerating the
golden fixtures (and review/sign-off), never silently loosening the
tolerance here.
"""
import json
from pathlib import Path

import pytest

from tests.golden.capture_golden import _clean
from tests.golden.capture_engine import capture_engine
from tests.golden.fake_feed import FakeFeed

INSTRUMENTS = ["usdclp", "gold", "nasdaq"]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

FLOAT_TOL = 1e-9


def _is_numeric_non_bool(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def assert_recursive_equal(actual, expected, path="$"):
    """Recursively compare `actual` (freshly captured) against `expected`
    (loaded from the committed golden JSON), raising an AssertionError that
    names the JSON path and both values on the first mismatch found.
    """
    # bool is a subclass of int in Python — compare bool-ness explicitly so
    # True/False never silently compares equal to 1/0.
    if isinstance(actual, bool) or isinstance(expected, bool):
        assert isinstance(actual, bool) and isinstance(expected, bool), (
            f"Type mismatch at {path}: actual={actual!r} ({type(actual).__name__}), "
            f"expected={expected!r} ({type(expected).__name__})"
        )
        assert actual == expected, (
            f"Mismatch at {path}: actual={actual!r}, expected={expected!r}"
        )
        return

    if isinstance(expected, dict):
        assert isinstance(actual, dict), (
            f"Type mismatch at {path}: actual={actual!r} ({type(actual).__name__}), "
            f"expected is dict"
        )
        assert set(actual.keys()) == set(expected.keys()), (
            f"Key mismatch at {path}: actual keys={sorted(actual.keys())}, "
            f"expected keys={sorted(expected.keys())}"
        )
        for key in expected:
            assert_recursive_equal(actual[key], expected[key], f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), (
            f"Type mismatch at {path}: actual={actual!r} ({type(actual).__name__}), "
            f"expected is list"
        )
        assert len(actual) == len(expected), (
            f"Length mismatch at {path}: actual len={len(actual)}, "
            f"expected len={len(expected)}"
        )
        for i, (a_item, e_item) in enumerate(zip(actual, expected)):
            assert_recursive_equal(a_item, e_item, f"{path}[{i}]")
        return

    if _is_numeric_non_bool(expected) and _is_numeric_non_bool(actual):
        assert abs(actual - expected) <= FLOAT_TOL, (
            f"Numeric mismatch at {path}: actual={actual!r}, expected={expected!r}, "
            f"diff={abs(actual - expected)!r} > tol={FLOAT_TOL}"
        )
        return

    # ints / strings / enums / None: exact equality (also catches type
    # mismatches between e.g. str and None, dict/list vs scalar, etc.)
    assert type(actual) is type(expected) and actual == expected, (
        f"Mismatch at {path}: actual={actual!r} ({type(actual).__name__}), "
        f"expected={expected!r} ({type(expected).__name__})"
    )


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_parity_against_golden(instrument):
    # Apply the same canonicalization (numpy-scalar unwrapping + 6-decimal
    # float rounding) used when the golden fixtures were generated, so the
    # comparison is against the same representation, not raw float noise
    # from repr/serialization round-tripping. See `to_canonical_json`.
    actual = _clean(capture_engine(instrument, FakeFeed()))

    fixture_path = FIXTURES_DIR / f"{instrument}.json"
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert_recursive_equal(actual, expected)
