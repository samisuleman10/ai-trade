from ai_trade.market_data import OHLCVBar, validate_bars
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, heikin_ashi, smma


def bar(index: int, price: float) -> OHLCVBar:
    return OHLCVBar(
        timestamp=f"2026-01-01T{index:02d}:00:00Z",
        open=price,
        high=price + 1,
        low=price - 1,
        close=price + 0.5,
        volume=1000,
    )


def test_smma_has_no_value_until_its_seed_window() -> None:
    values = smma([1, 2, 3, 4, 5], 3)

    assert values[:2] == [None, None]
    assert values[2] == 2
    assert values[3] == 8 / 3


def test_heikin_ashi_uses_previous_heikin_values() -> None:
    result = heikin_ashi([bar(0, 10), bar(1, 12)])

    assert result[0] == (10.25, 10.125)
    assert result[1][0] == 10.1875


def test_alligator_display_offsets_do_not_read_future_bars() -> None:
    rows = [bar(index, 100 + index) for index in range(30)]
    points = alligator_points(rows, Strategy01Parameters(slope_lookback_bars=1))

    assert points[12].jaw is None  # 13-period seed at index 12 is only displayed 8 bars later.
    assert points[20].jaw is not None
    assert points[20].jaw == sum((rows[index].high + rows[index].low) / 2 for index in range(13)) / 13


def test_validation_rejects_duplicate_timestamps() -> None:
    report = validate_bars([bar(0, 100), bar(0, 101)])

    assert report["valid"] is False
    assert report["duplicate_timestamps"] == 1
