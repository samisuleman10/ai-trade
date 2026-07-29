from ai_trade.strategy_04_audit import (
    CheckResult,
    FifteenMinuteBar,
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


SLIPPAGE_BPS = 1.0
SLIPPAGE_FRACTION = SLIPPAGE_BPS / 10_000.0

# Fills are deterministic in backtest_strategy_01._fill: an entry fills at the
# next 15-minute bar's OPEN and a level exit fills AT the level, each with one
# side of slippage applied against the position, never at a gapped-through
# price. The clean fixture therefore derives every price from that arithmetic.
ENTRY_BAR_OPEN = 437.9
LONG_ENTRY = ENTRY_BAR_OPEN * (1 + SLIPPAGE_FRACTION)
SHORT_ENTRY = ENTRY_BAR_OPEN * (1 - SLIPPAGE_FRACTION)
LONG_STOP = 436.95
LONG_TARGET = LONG_ENTRY + (LONG_ENTRY - LONG_STOP)
LONG_TARGET_FILL = LONG_TARGET * (1 - SLIPPAGE_FRACTION)
LONG_STOP_FILL = LONG_STOP * (1 - SLIPPAGE_FRACTION)

QUANTITY = 100
RESULT_R = 0.97
PLANNED_RISK = abs(LONG_ENTRY - LONG_STOP) * QUANTITY
NET_PNL = RESULT_R * PLANNED_RISK


def _trade(**overrides) -> TradeRecord:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        exit_timestamp="2021-08-03T15:45:00Z",
        side="long",
        quantity=QUANTITY,
        entry_price=LONG_ENTRY,
        stop_price=LONG_STOP,
        target_price=LONG_TARGET,
        exit_price=LONG_TARGET_FILL,
        exit_reason="target",
        net_pnl=NET_PNL,
        result_r=RESULT_R,
    )
    values.update(overrides)
    return TradeRecord(**values)


BARS = [
    FifteenMinuteBar("2021-08-03T14:15:00Z", 437.5),
    FifteenMinuteBar("2021-08-03T14:30:00Z", ENTRY_BAR_OPEN),
    FifteenMinuteBar("2021-08-03T14:45:00Z", 438.2),
]


def _result(results: list[CheckResult], check_id: str) -> CheckResult:
    return next(item for item in results if item.check_id == check_id)


def test_clean_trade_passes_every_check():
    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert [item.check_id for item in results if not item.passed] == []


def test_atr_stamped_at_the_decision_timestamp_passes_causality():
    signal = _signal(one_hour_atr_timestamp="2021-08-03T14:30:00Z")
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "causality_atr").passed is True


def test_atr_stamped_after_the_decision_timestamp_fails_causality():
    signal = _signal(one_hour_atr_timestamp="2021-08-03T14:45:00Z")
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "causality_atr").passed is False


def test_zone_qualified_after_trigger_fails_causality():
    results = audit_trade(_signal(), _trade(), "2021-08-03T14:45:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "causality_zone").passed is False


def test_zone_qualified_exactly_at_trigger_timestamp_passes_causality():
    signal = _signal()
    results = audit_trade(signal, _trade(), signal.trigger_timestamp, BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "causality_zone").passed is True


def test_stop_buffer_must_be_five_percent_of_atr():
    results = audit_trade(_signal(stop_buffer=0.09), _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "stop_buffer").passed is False


def test_long_stop_sits_below_zone_lower_by_the_buffer():
    results = audit_trade(_signal(), _trade(stop_price=436.50), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "stop_price").passed is False


def test_entry_must_be_the_next_fifteen_minute_bar():
    trade = _trade(entry_timestamp="2021-08-03T14:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:45:00Z"), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_timing").passed is False


def test_long_entry_price_is_the_bar_open_plus_slippage():
    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is True


def test_long_entry_at_the_raw_bar_open_fails_entry_price():
    """A long buys in, so its fill must be the open moved UP by slippage."""

    trade = _trade(entry_price=ENTRY_BAR_OPEN)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is False


def test_short_entry_price_is_the_bar_open_less_slippage():
    signal = _signal(side="short", zone_side="supply")
    trade = _trade(side="short", entry_price=SHORT_ENTRY)
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is True


def test_short_entry_with_slippage_added_fails_entry_price():
    """Slipping a short entry upward would flatter the trade, not cost it."""

    signal = _signal(side="short", zone_side="supply")
    trade = _trade(side="short", entry_price=LONG_ENTRY)
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is False


def test_entry_price_from_an_unrelated_level_fails():
    trade = _trade(entry_price=999.0)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is False


def test_entry_price_with_no_bar_at_the_entry_timestamp_fails():
    """Missing evidence fails: an unverifiable anchor is not a passing one."""

    trade = _trade(entry_timestamp="2021-08-03T16:00:00Z")
    signal = _signal(entry_timestamp="2021-08-03T16:00:00Z")
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "entry_price").passed is False


def test_target_must_be_one_r_from_entry():
    results = audit_trade(_signal(), _trade(target_price=440.0), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "target_price").passed is False


def test_penetration_exactly_at_the_limit_passes():
    signal = _signal(long_zone_penetration_fraction=0.25)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is True


def test_penetration_just_inside_tolerance_passes():
    signal = _signal(long_zone_penetration_fraction=0.2500001)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is True


def test_penetration_beyond_the_limit_fails():
    signal = _signal(long_zone_penetration_fraction=0.250002)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is False


def test_long_with_no_recorded_penetration_fails():
    signal = _signal(long_zone_penetration_fraction=None)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is False


def test_version_with_no_penetration_rule_passes_with_no_recorded_fraction():
    """v1 has no penetration rule at all: max_long_penetration=None means the

    check must not fail a long trade just because the column never existed.
    """
    signal = _signal(long_zone_penetration_fraction=None)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, None, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is True


def test_version_with_no_penetration_rule_passes_even_with_a_recorded_fraction():
    """A None rule is a property of the version, not of the individual trade,

    so it stays inapplicable even if a fraction happens to be present.
    """
    signal = _signal(long_zone_penetration_fraction=0.9)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", BARS, None, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is True


def test_short_trades_skip_the_penetration_gate():
    signal = _signal(side="short", zone_side="supply", long_zone_penetration_fraction=0.9)
    trade = _trade(side="short", stop_price=437.95, entry_price=436.95, target_price=435.95, exit_price=435.9)
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "penetration").passed is True


def test_entry_before_ten_thirty_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T14:15:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:15:00Z"), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "session").passed is False


def test_entry_exactly_at_ten_thirty_new_york_passes_session():
    trade = _trade(entry_timestamp="2021-08-03T14:30:00Z")
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "session").passed is True


def test_entry_exactly_at_fifteen_hundred_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T19:00:00Z", exit_timestamp="2021-08-03T19:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T19:00:00Z"), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "session").passed is False


def test_stop_exit_priced_at_the_target_fails_outcome():
    trade = _trade(exit_reason="stop", exit_price=438.99)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_friday_entry_fails_session():
    trade = _trade(entry_timestamp="2021-08-06T14:30:00Z", exit_timestamp="2021-08-06T15:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-06T14:30:00Z"), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "session").passed is False


def test_target_exit_below_target_price_fails_outcome():
    results = audit_trade(_signal(), _trade(exit_price=438.0), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_long_target_exit_at_the_slipped_level_passes_outcome():
    trade = _trade(target_price=LONG_TARGET, exit_price=LONG_TARGET_FILL)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is True


def test_target_exit_worse_by_far_more_than_slippage_fails_outcome():
    exit_price = LONG_TARGET - LONG_TARGET * SLIPPAGE_FRACTION * 50
    trade = _trade(target_price=LONG_TARGET, exit_price=exit_price)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_long_stop_exit_at_the_slipped_level_passes_outcome():
    trade = _trade(exit_reason="stop", stop_price=LONG_STOP, exit_price=LONG_STOP_FILL)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is True


def test_stop_exit_worse_by_far_more_than_slippage_fails_outcome():
    exit_price = LONG_STOP - LONG_STOP * SLIPPAGE_FRACTION * 50
    trade = _trade(exit_reason="stop", stop_price=LONG_STOP, exit_price=exit_price)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_long_target_exit_far_above_the_target_fails_outcome():
    """A target exit had NO upper bound: 10x the target used to pass."""

    trade = _trade(target_price=LONG_TARGET, exit_price=LONG_TARGET * 10)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_short_target_exit_far_below_the_target_fails_outcome():
    """The mirror-image hole on the short side: 0.1x the target used to pass."""

    signal = _signal(side="short", zone_side="supply")
    target_price = 435.95
    trade = _trade(
        side="short",
        entry_price=436.95,
        stop_price=437.95,
        target_price=target_price,
        exit_reason="target",
        exit_price=target_price * 0.1,
    )
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_long_target_exit_at_the_unslipped_level_fails_outcome():
    """Slippage is not optional: the level itself is the wrong recorded fill."""

    trade = _trade(target_price=LONG_TARGET, exit_price=LONG_TARGET)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_long_stop_exit_at_the_unslipped_level_fails_outcome():
    trade = _trade(exit_reason="stop", stop_price=LONG_STOP, exit_price=LONG_STOP)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is False


def test_short_stop_exit_fills_at_the_level_plus_slippage():
    signal = _signal(side="short", zone_side="supply")
    stop_price = 437.95
    trade = _trade(
        side="short",
        entry_price=436.95,
        stop_price=stop_price,
        target_price=435.95,
        exit_reason="stop",
        exit_price=stop_price * (1 + SLIPPAGE_FRACTION),
    )
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is True


def test_weekend_close_makes_no_level_assertion():
    """Weekend closes fill at the bar close, which the audit cannot see."""

    trade = _trade(exit_reason="weekend_close", exit_price=1.0)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "outcome").passed is True


def test_result_r_is_not_a_strategy_04_check_any_more():
    """It moved to ledger_audit, which applies the contract multiplier.

    Emitting it here as well would publish two result_r checks per trade
    into one trade_audit entry, and the two could disagree -- which is the
    drift this consolidation exists to prevent.
    """

    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert [item for item in results if item.check_id == "result_r"] == []


def test_strategy_04_emits_the_shared_check_result_type():
    """Both audits feed one dataset, so they must emit one type, not two alike."""

    from ai_trade.ledger_audit import CheckResult as SharedCheckResult

    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert CheckResult is SharedCheckResult
    assert all(isinstance(item, SharedCheckResult) for item in results)


def test_demand_zone_with_short_side_fails_side_match():
    signal = _signal(side="short", zone_side="demand")
    results = audit_trade(signal, _trade(side="short"), "2021-08-03T13:00:00Z", BARS, 0.25, SLIPPAGE_BPS)
    assert _result(results, "side_match").passed is False
