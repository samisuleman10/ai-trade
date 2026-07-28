from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_02_v1_3 import Strategy02V13Parameters, hourly_structure_points


def bars(prices: list[float]) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return [OHLCVBar((start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    p, p + .5, p - .5, p, 1000) for i, p in enumerate(prices)]


def test_hourly_structure_needs_depth_and_backstep_confirmation() -> None:
    rows = bars([15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,2,3,4,5,6,7])
    p = Strategy02V13Parameters(zigzag_depth=10, zigzag_backstep=3, zigzag_deviation=5)
    points = hourly_structure_points(rows, p)
    assert all(point.support is None for point in points[:17])
    assert points[17].support == .49
    assert points[17].support_pivot_timestamp == rows[14].timestamp


def test_hourly_support_is_invalidated_by_completed_hourly_wick() -> None:
    rows = bars([15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,2,3,4,5,0,1,2,3])
    p = Strategy02V13Parameters(zigzag_depth=10, zigzag_backstep=3, zigzag_deviation=5)
    points = hourly_structure_points(rows, p)
    assert points[17].support == .49
    assert points[19].support is None


def test_course_zigzag_defaults_are_locked() -> None:
    p = Strategy02V13Parameters()
    assert (p.zigzag_depth, p.zigzag_deviation, p.zigzag_backstep) == (18, 5, 3)
