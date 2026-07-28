from datetime import datetime, timedelta, timezone

import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_02 import CambistParameters, cambist_points, heikin_ashi_bars, rsi


def bars_from_prices(prices: list[float]) -> list[OHLCVBar]:
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


def test_heikin_ashi_ohlc_is_causal() -> None:
    result = heikin_ashi_bars(bars_from_prices([10, 12]))
    assert result[0].open == 10
    assert result[0].close == 10
    assert result[1].open == 10
    assert result[1].high == 12.5


def test_rsi_waits_for_seed_window() -> None:
    values = rsi([1, 2, 3, 2, 4], period=3)
    assert values[:3] == [None, None, None]
    assert values[3] is not None


def test_support_appears_only_after_confirmation() -> None:
    rows = bars_from_prices([10, 9, 8, 7, 8, 9, 10])
    points = cambist_points(rows, CambistParameters(rsi_period=2, pivot_left=2, pivot_right=2))
    assert points[4].support is None
    assert points[5].support == 6.5
    assert points[5].support_pivot_timestamp == rows[3].timestamp
    assert points[5].support_confirmed_timestamp == rows[5].timestamp
    assert points[5].new_support is True
    assert points[6].new_support is False


def test_future_bars_do_not_change_confirmed_prefix() -> None:
    prefix = bars_from_prices([10, 9, 8, 7, 8, 9, 10, 11])
    future = [
        OHLCVBar("2026-01-05T16:30:00Z", 100, 101, 99, 100, 1000),
        OHLCVBar("2026-01-05T16:45:00Z", 50, 51, 49, 50, 1000),
    ]
    params = CambistParameters(rsi_period=2, pivot_left=2, pivot_right=2)
    before = cambist_points(prefix, params)
    after = cambist_points(prefix + future, params)
    assert before == after[: len(prefix)]


def test_zero_right_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="pivot_left and pivot_right"):
        CambistParameters(pivot_right=0)
