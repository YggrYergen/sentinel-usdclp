"""
Acceptance gate for Task 0.1 / P1 Task 1.6b: capturing the golden master
twice from the same committed fixture must produce BYTE-IDENTICAL canonical
JSON, for all three target instruments (usdclp, gold, nasdaq). As of Task
1.6b this drives the headless `sentinel_engine.engine.Engine` via
`capture_engine`, matching the repointed parity gate.
"""
import pytest

from tests.golden.capture_engine import capture_engine
from tests.golden.capture_golden import to_canonical_json
from tests.golden.fake_feed import FakeFeed

INSTRUMENTS = ["usdclp", "gold", "nasdaq"]


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_capture_is_deterministic(instrument):
    result_1 = capture_engine(instrument, FakeFeed())
    result_2 = capture_engine(instrument, FakeFeed())

    json_1 = to_canonical_json(result_1)
    json_2 = to_canonical_json(result_2)

    assert json_1 == json_2
