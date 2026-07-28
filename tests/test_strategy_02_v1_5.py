from ai_trade.strategy_02_v1_5 import Strategy02V15Parameters, _hourly_cross


def test_hourly_cross_requires_open_and_close_on_opposite_sides() -> None:
    assert _hourly_cross(99, 101, 100) == "long"
    assert _hourly_cross(101, 99, 100) == "short"
    assert _hourly_cross(101, 100.5, 100) is None
    assert _hourly_cross(99, 99.5, 100) is None


def test_v15_locks_zigzag_defaults_for_15m_structure() -> None:
    p = Strategy02V15Parameters()
    assert (p.zigzag_depth, p.zigzag_deviation, p.zigzag_backstep) == (18, 5, 3)
