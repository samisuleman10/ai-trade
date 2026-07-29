"""Per-trade correctness checks for Strategy 04 historical results.

Every function is pure. A failing check means the backtest is wrong, not that
the trade was unprofitable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EASTERN = ZoneInfo("America/New_York")
TOLERANCE = 1e-6
STOP_BUFFER_ATR_FRACTION = 0.05
SESSION_START_MINUTES = 10 * 60 + 30
SESSION_END_MINUTES = 15 * 60


@dataclass(frozen=True)
class SignalRecord:
    decision_timestamp: str
    entry_timestamp: str
    side: str
    zone_id: int
    zone_side: str
    zone_lower: float
    zone_upper: float
    trigger_timestamp: str
    trigger_low: float
    one_hour_atr: float
    one_hour_atr_timestamp: str
    stop_buffer: float
    long_zone_penetration_fraction: Optional[float]
    reward_to_risk: float


@dataclass(frozen=True)
class TradeRecord:
    decision_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    side: str
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    result_r: float


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    expected: str
    actual: str


def _parse(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= TOLERANCE


def _check(check_id: str, passed: bool, expected: object, actual: object) -> CheckResult:
    return CheckResult(check_id, passed, str(expected), str(actual))


def check_causality_atr(signal: SignalRecord) -> CheckResult:
    """The ATR must have been available by the time the decision was made.

    ``one_hour_atr_timestamp`` is the CLOSE time of the one-hour bar that
    produced the ATR value (see ``_hourly_atr_timeline`` in
    strategy_04_v1.py). The decision is made at the trigger bar's close,
    which equals ``decision_timestamp``. Comparing the ATR close against the
    trigger bar's OPEN time (``trigger_timestamp``) would mix two different
    timestamp conventions, so this check compares against
    ``decision_timestamp`` instead.
    """

    passed = _parse(signal.one_hour_atr_timestamp) <= _parse(signal.decision_timestamp)
    return _check(
        "causality_atr",
        passed,
        "atr bar at or before " + signal.decision_timestamp,
        signal.one_hour_atr_timestamp,
    )


def check_causality_zone(signal: SignalRecord, zone_qualified_timestamp: str) -> CheckResult:
    """The zone must have qualified before the trigger bar opened.

    A zone qualified exactly when the trigger bar opened was already known
    at that instant, so the boundary is inclusive.
    """

    if not zone_qualified_timestamp:
        return _check("causality_zone", False, "a qualification timestamp", "missing")
    passed = _parse(zone_qualified_timestamp) <= _parse(signal.trigger_timestamp)
    return _check(
        "causality_zone",
        passed,
        "qualified at or before " + signal.trigger_timestamp,
        zone_qualified_timestamp,
    )


def check_stop_buffer(signal: SignalRecord) -> CheckResult:
    """The stop buffer is 0.05 x the latest completed one-hour ATR."""

    expected = STOP_BUFFER_ATR_FRACTION * signal.one_hour_atr
    return _check("stop_buffer", _close(expected, signal.stop_buffer), expected, signal.stop_buffer)


def check_stop_price(signal: SignalRecord, trade: TradeRecord) -> CheckResult:
    """The stop sits beyond the zone by exactly the buffer."""

    if trade.side == "long":
        expected = signal.zone_lower - signal.stop_buffer
    else:
        expected = signal.zone_upper + signal.stop_buffer
    return _check("stop_price", _close(expected, trade.stop_price), expected, trade.stop_price)


def check_entry_timing(
    trade: TradeRecord,
    signal: SignalRecord,
    fifteen_minute_timestamps: Sequence[str],
) -> CheckResult:
    """Entry is the next 15-minute bar that opens after the trigger bar."""

    ordered = sorted(fifteen_minute_timestamps)
    later = [value for value in ordered if _parse(value) > _parse(signal.trigger_timestamp)]
    if not later:
        return _check("entry_timing", False, "a bar after the trigger", "none available")
    expected = later[0]
    return _check("entry_timing", expected == trade.entry_timestamp, expected, trade.entry_timestamp)


def check_target_price(signal: SignalRecord, trade: TradeRecord) -> CheckResult:
    """The target is one risk unit from entry, in the trade's direction."""

    distance = abs(trade.entry_price - trade.stop_price)
    if trade.side == "long":
        expected = trade.entry_price + distance
    else:
        expected = trade.entry_price - distance
    passed = _close(expected, trade.target_price) and _close(signal.reward_to_risk, 1.0)
    return _check("target_price", passed, expected, trade.target_price)


def check_penetration(signal: SignalRecord, max_long_penetration: Optional[float]) -> CheckResult:
    """Version 1.1 caps how far a long trigger may travel into demand.

    ``max_long_penetration=None`` means the strategy version being audited
    (v1) has no penetration rule at all -- ``long_zone_penetration_fraction``
    is not even a column in v1's ``candidate_signals.csv``. Failing a v1 long
    trade for lacking evidence of a rule that version never had would be a
    false accusation, so the check passes and says so explicitly.

    When a rule does apply (``max_long_penetration`` is a number), a missing
    fraction still fails: the rule exists but the evidence backing it is
    absent, which is itself a defect worth surfacing.
    """

    if signal.side != "long":
        return _check("penetration", True, "not applicable to shorts", signal.side)
    if max_long_penetration is None:
        return _check(
            "penetration",
            True,
            "not applicable: this version has no penetration rule",
            signal.long_zone_penetration_fraction,
        )
    if signal.long_zone_penetration_fraction is None:
        return _check("penetration", False, "a recorded penetration fraction", "missing")
    passed = signal.long_zone_penetration_fraction <= max_long_penetration + TOLERANCE
    return _check(
        "penetration",
        passed,
        "at most " + str(max_long_penetration),
        signal.long_zone_penetration_fraction,
    )


def check_session(trade: TradeRecord) -> CheckResult:
    """Entries are Monday to Thursday, from 10:30 up to but not including 15:00."""

    local = _parse(trade.entry_timestamp).astimezone(EASTERN)
    minutes = local.hour * 60 + local.minute
    passed = local.weekday() < 4 and SESSION_START_MINUTES <= minutes < SESSION_END_MINUTES
    return _check(
        "session",
        passed,
        "monday-thursday, 10:30 to 15:00 new york",
        local.strftime("%a %H:%M"),
    )


def check_outcome(trade: TradeRecord, slippage_bps: float) -> CheckResult:
    """The recorded exit price must be the exact fill the level implies.

    ``backtest_strategy_01._fill`` is deterministic and models no gaps: a
    stop or target exit always fills AT the level with one side of
    slippage applied against the position. So there is exactly one correct
    exit price per (level, side), and exact equality within ``TOLERANCE``
    is the right assertion -- it cannot produce a false positive.

    A band would be strictly weaker, and the band this replaced had no
    upper bound on a target at all: a long "target" exit recorded at ten
    times the target price passed, because finishing "better than target"
    was treated as unbounded-acceptable. Nothing in the producer can
    finish better than the target, so that leniency only ever hid bugs.

    Any other reason (``weekend_close``) fills at a bar close the audit
    never sees, so it asserts no level -- as before.
    """

    if trade.exit_reason == "target":
        level = trade.target_price
    elif trade.exit_reason == "stop":
        level = trade.stop_price
    else:
        return _check("outcome", True, "no level assertion", trade.exit_reason)

    fraction = slippage_bps / 10_000.0
    # Exiting a long means selling (fill below the level); exiting a short
    # means buying it back (fill above the level).
    expected = level * (1 - fraction) if trade.side == "long" else level * (1 + fraction)
    return _check("outcome", _close(expected, trade.exit_price), expected, trade.exit_price)


def check_side_match(signal: SignalRecord) -> CheckResult:
    """Demand zones support longs; supply zones support shorts."""

    expected = "demand" if signal.side == "long" else "supply"
    return _check("side_match", expected == signal.zone_side, expected, signal.zone_side)


def audit_trade(
    signal: SignalRecord,
    trade: TradeRecord,
    zone_qualified_timestamp: str,
    fifteen_minute_timestamps: Sequence[str],
    max_long_penetration: Optional[float],
    slippage_bps: float,
) -> list[CheckResult]:
    """Run every check for one trade, in stable order."""

    return [
        check_causality_atr(signal),
        check_causality_zone(signal, zone_qualified_timestamp),
        check_stop_buffer(signal),
        check_stop_price(signal, trade),
        check_entry_timing(trade, signal, fifteen_minute_timestamps),
        check_target_price(signal, trade),
        check_penetration(signal, max_long_penetration),
        check_session(trade),
        check_outcome(trade, slippage_bps),
        check_side_match(signal),
    ]
