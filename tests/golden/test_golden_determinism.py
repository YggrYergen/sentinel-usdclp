"""
Acceptance gate for Task 0.1: capturing the golden master twice from the
same committed fixture must produce BYTE-IDENTICAL canonical JSON, for
all three target instruments (usdclp, gold, nasdaq).
"""
import pytest

from tests.golden.capture_golden import capture_golden, to_canonical_json
from tests.golden.fake_feed import FakeFeed

INSTRUMENTS = ["usdclp", "gold", "nasdaq"]


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_capture_is_deterministic(instrument):
    result_1 = capture_golden(instrument, FakeFeed())
    result_2 = capture_golden(instrument, FakeFeed())

    json_1 = to_canonical_json(result_1)
    json_2 = to_canonical_json(result_2)

    assert json_1 == json_2
