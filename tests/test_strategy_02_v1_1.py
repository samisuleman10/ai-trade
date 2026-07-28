from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_02_v1_1 import Strategy02V11Parameters, structure_points


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


def test_support_dot_is_below_the_pivot_wick() -> None:
    rows = bars([10, 9, 8, 7, 8, 9, 10])
    params = Strategy02V11Parameters(pivot_left=2, pivot_right=2, minimum_tick=0.01)
    point = structure_points(rows, params)[5]
    assert point.support == 6.49
    assert point.support < rows[3].low


def test_final_equal_low_in_cluster_becomes_support() -> None:
    rows = bars([10, 9, 8, 7, 7, 8, 9, 10])
    params = Strategy02V11Parameters(pivot_left=2, pivot_right=2, minimum_tick=0.01)
    points = structure_points(rows, params)
    assert points[5].support is None
    assert points[6].support == 6.49
    assert points[6].support_pivot_timestamp == rows[4].timestamp
