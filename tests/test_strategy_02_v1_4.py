from ai_trade.strategy_02_v1_4 import Strategy02V14Parameters


def test_v14_keeps_course_zigzag_and_heikin_ashi_defaults() -> None:
    params = Strategy02V14Parameters()
    assert (params.zigzag_depth, params.zigzag_deviation, params.zigzag_backstep) == (18, 5, 3)
    assert params.trigger_with_heikin_ashi is True
