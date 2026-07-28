from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_02_v1 import Strategy02Parameters, structure_points


def bars(prices: list[float]) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return [
        OHLCVBar(
            timestamp=(start + timedelta(minutes=15 * index)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            open=price,
            high=price + 0.5,
            low=price - 0.5,
            close=price,
            volume=1000,
        )
        for index, price in enumerate(prices)
    ]


def test_support_is_not_available_before_confirmation() -> None:
    rows = bars([10, 9, 8, 7, 8, 9, 10])
    points = structure_points(rows, Strategy02Parameters(pivot_left=2, pivot_right=2))
    assert points[4].support is None
    assert points[5].support == 6.5
    assert points[5].support_pivot_timestamp == rows[3].timestamp
    assert points[5].support_confirmed_timestamp == rows[5].timestamp


def test_future_bars_do_not_change_completed_history() -> None:
    original = bars([10, 9, 8, 7, 8, 9, 10, 11])
    future = [OHLCVBar("2026-01-05T16:30:00Z", 100, 101, 99, 100, 1000)]
    params = Strategy02Parameters(pivot_left=2, pivot_right=2)
    assert structure_points(original, params) == structure_points(original + future, params)[: len(original)]
