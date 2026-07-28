from ai_trade.strategy_04_audit import (
    CheckResult,
    SignalRecord,
    TradeRecord,
    audit_trade,
)


def _signal(**overrides) -> SignalRecord:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        side="long",
        zone_id=39,
        zone_side="demand",
        zone_lower=437.0,
        zone_upper=437.9,
        trigger_timestamp="2021-08-03T14:15:00Z",
        trigger_low=437.5,
        one_hour_atr=1.0,
        one_hour_atr_timestamp="2021-08-03T14:00:00Z",
        stop_buffer=0.05,
        long_zone_penetration_fraction=0.2,
        reward_to_risk=1.0,
    )
    values.update(overrides)
    return SignalRecord(**values)


def _trade(**overrides) -> TradeRecord:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        exit_timestamp="2021-08-03T15:45:00Z",
        side="long",
        entry_price=437.95,
        stop_price=436.95,
        target_price=438.95,
        exit_price=438.99,
        exit_reason="target",
        result_r=0.97,
    )
    values.update(overrides)
    return TradeRecord(**values)


TIMESTAMPS = [
    "2021-08-03T14:15:00Z",
    "2021-08-03T14:30:00Z",
    "2021-08-03T14:45:00Z",
]


def _result(results: list[CheckResult], check_id: str) -> CheckResult:
    return next(item for item in results if item.check_id == check_id)


def test_clean_trade_passes_every_check():
    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert [item.check_id for item in results if not item.passed] == []


def test_atr_taken_from_the_trigger_bar_fails_causality():
    signal = _signal(one_hour_atr_timestamp="2021-08-03T14:15:00Z")
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "causality_atr").passed is False


def test_zone_qualified_after_trigger_fails_causality():
    results = audit_trade(_signal(), _trade(), "2021-08-03T14:45:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "causality_zone").passed is False


def test_stop_buffer_must_be_five_percent_of_atr():
    results = audit_trade(_signal(stop_buffer=0.09), _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "stop_buffer").passed is False


def test_long_stop_sits_below_zone_lower_by_the_buffer():
    results = audit_trade(_signal(), _trade(stop_price=436.50), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "stop_price").passed is False


def test_entry_must_be_the_next_fifteen_minute_bar():
    trade = _trade(entry_timestamp="2021-08-03T14:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:45:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "entry_timing").passed is False


def test_target_must_be_one_r_from_entry():
    results = audit_trade(_signal(), _trade(target_price=440.0), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "target_price").passed is False


def test_penetration_exactly_at_the_limit_passes():
    signal = _signal(long_zone_penetration_fraction=0.25)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is True


def test_penetration_just_inside_tolerance_passes():
    signal = _signal(long_zone_penetration_fraction=0.2500001)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is True


def test_penetration_beyond_the_limit_fails():
    signal = _signal(long_zone_penetration_fraction=0.250002)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is False


def test_short_trades_skip_the_penetration_gate():
    signal = _signal(side="short", zone_side="supply", long_zone_penetration_fraction=0.9)
    trade = _trade(side="short", stop_price=437.95, entry_price=436.95, target_price=435.95, exit_price=435.9)
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is True


def test_entry_before_ten_thirty_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T14:15:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:15:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_entry_exactly_at_ten_thirty_new_york_passes_session():
    trade = _trade(entry_timestamp="2021-08-03T14:30:00Z")
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is True


def test_entry_exactly_at_fifteen_hundred_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T19:00:00Z", exit_timestamp="2021-08-03T19:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T19:00:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_stop_exit_priced_at_the_target_fails_outcome():
    trade = _trade(exit_reason="stop", exit_price=438.99)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "outcome").passed is False


def test_friday_entry_fails_session():
    trade = _trade(entry_timestamp="2021-08-06T14:30:00Z", exit_timestamp="2021-08-06T15:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-06T14:30:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_target_exit_below_target_price_fails_outcome():
    results = audit_trade(_signal(), _trade(exit_price=438.0), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "outcome").passed is False


def test_demand_zone_with_short_side_fails_side_match():
    signal = _signal(side="short", zone_side="demand")
    results = audit_trade(signal, _trade(side="short"), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "side_match").passed is False
