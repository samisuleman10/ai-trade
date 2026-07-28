from ai_trade.strategy_02_v2 import Strategy02V2Parameters


def test_vix_filter_threshold_defaults_to_below_twenty() -> None:
    assert Strategy02V2Parameters().vix_threshold == 20.0
