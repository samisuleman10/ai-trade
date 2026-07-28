from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_02_v1 import _heikin_ashi
from ai_trade.strategy_02_v1_2 import Strategy02V12Parameters, structure_points


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


def test_broken_support_disappears_on_breaking_wick() -> None:
    rows = bars([10, 9, 8, 7, 8, 9, 10, 6, 7, 8, 9])
    params = Strategy02V12Parameters(pivot_left=2, pivot_right=2, minimum_tick=0.01)
    points = structure_points(rows, params)
    assert points[5].support == 6.49
    assert points[7].support is None


def test_every_displayed_level_stays_outside_current_wick() -> None:
    rows = bars([10, 9, 8, 7, 7, 8, 9, 6, 7, 8, 9, 10])
    params = Strategy02V12Parameters(pivot_left=2, pivot_right=2, minimum_tick=0.01)
    points = structure_points(rows, params)
    ha = _heikin_ashi(rows)
    for point, candle in zip(points, ha):
        assert point.support is None or point.support < candle[2]
        assert point.resistance is None or point.resistance > candle[1]
