from ai_trade.validate_strategy_02_v1_5 import _percentile


def test_percentile_interpolates_deterministically() -> None:
    assert _percentile([0.0, 10.0], 0.5) == 5.0
    assert _percentile([1.0, 2.0, 3.0], 0.0) == 1.0
    assert _percentile([1.0, 2.0, 3.0], 1.0) == 3.0
