"""Strategy 04 v1: causal 1-hour zones with 15-minute reaction entries.

The one-hour indicator decides *where* a setup may exist. This module decides
*when* a completed 15-minute candle confirms a reaction. It creates historical
research signals only; it has no broker or order-submission capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import atr
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    Strategy04IndicatorResult,
    ZoneEvent,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class Strategy04ExecutionParameters:
    """Locked first-pass execution rules for the 15-minute layer."""

    entry_interval_minutes: int = 15
    one_hour_interval_minutes: int = 60
    one_hour_atr_period: int = 14
    stop_buffer_one_hour_atr: float = 0.05
    require_directional_body: bool = True
    require_valid_side_approach: bool = True
    one_signal_per_zone: bool = True

    def __post_init__(self) -> None:
        if min(
            self.entry_interval_minutes,
            self.one_hour_interval_minutes,
            self.one_hour_atr_period,
        ) < 1:
            raise ValueError("Timeframes and ATR period must be positive")
        if self.stop_buffer_one_hour_atr < 0:
            raise ValueError("Stop buffer cannot be negative")


@dataclass
class _TimelineZone:
    zone_id: int
    side: str
    lower: float
    upper: float
    qualification_score: int
    current_score: int
    status: str
    active: bool = True


@dataclass(frozen=True)
class Strategy04SignalResult:
    signals: list[dict[str, object]]
    indicator: Strategy04IndicatorResult


def _parse(value: str) -> datetime:
    return datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _format(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(UTC_FORMAT)


def _bar_close(bar: OHLCVBar, minutes: int) -> datetime:
    return _parse(bar.timestamp) + timedelta(minutes=minutes)


def _hourly_atr_timeline(
    bars: list[OHLCVBar],
    period: int,
    interval_minutes: int,
) -> list[tuple[datetime, float]]:
    values = atr(bars, period)
    return [
        (_bar_close(bar, interval_minutes), float(value))
        for bar, value in zip(bars, values)
        if value is not None and value > 0
    ]


def _apply_event(zones: dict[int, _TimelineZone], event: ZoneEvent) -> None:
    terminal = {"age_expired", "broken_zone_expired", "capacity_expired"}
    if event.event == "qualified":
        zones[event.zone_id] = _TimelineZone(
            zone_id=event.zone_id,
            side=event.side,
            lower=event.lower,
            upper=event.upper,
            qualification_score=event.score,
            current_score=event.score,
            status="active",
        )
        return

    zone = zones.get(event.zone_id)
    if zone is None:
        return
    zone.current_score = max(zone.current_score, event.score)
    if event.event == "broken":
        zone.status = "broken"
        zone.active = False
    elif event.event == "role_flip_retest":
        zone.side = event.side
        zone.lower = event.lower
        zone.upper = event.upper
        zone.status = "verified"
        zone.active = True
    elif event.event in terminal:
        zone.status = "expired"
        zone.active = False
    elif event.event == "touch":
        zone.status = "touched"
    elif event.event == "rejection":
        zone.status = "rejected"


def _reaction_matches(
    zone: _TimelineZone,
    previous: OHLCVBar,
    bar: OHLCVBar,
    params: Strategy04ExecutionParameters,
) -> bool:
    contact = bar.low <= zone.upper and bar.high >= zone.lower
    if not contact:
        return False
    if zone.side == "demand":
        approached = previous.close > zone.upper
        directional = bar.close > bar.open
        returned_outside = bar.close > zone.upper
    else:
        approached = previous.close < zone.lower
        directional = bar.close < bar.open
        returned_outside = bar.close < zone.lower
    return (
        returned_outside
        and (directional or not params.require_directional_body)
        and (approached or not params.require_valid_side_approach)
    )


def signals_from_zone_events(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    events: Iterable[ZoneEvent],
    params: Strategy04ExecutionParameters = Strategy04ExecutionParameters(),
) -> list[dict[str, object]]:
    """Create next-bar signals from zones known before each trigger bar starts.

    A zone event stamped at a 15-minute bar's close cannot affect that same bar.
    It becomes eligible starting with the next bar. The latest fully completed
    one-hour ATR at the decision time supplies the structural stop buffer.
    """

    entries = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    if len(entries) < 3 or not hours:
        return []

    ordered_events = sorted(list(events), key=lambda event: _parse(event.timestamp))
    atr_timeline = _hourly_atr_timeline(
        hours, params.one_hour_atr_period, params.one_hour_interval_minutes
    )
    live: dict[int, _TimelineZone] = {}
    used_zone_ids: set[int] = set()
    event_index = 0
    atr_index = -1
    latest_atr: Optional[float] = None
    latest_atr_timestamp: Optional[datetime] = None
    signals: list[dict[str, object]] = []

    for index in range(1, len(entries) - 1):
        previous, bar, next_bar = entries[index - 1], entries[index], entries[index + 1]
        bar_start = _parse(bar.timestamp)
        decision_time = _bar_close(bar, params.entry_interval_minutes)

        # Apply only information that existed before the trigger bar opened.
        while (
            event_index < len(ordered_events)
            and _parse(ordered_events[event_index].timestamp) <= bar_start
        ):
            _apply_event(live, ordered_events[event_index])
            event_index += 1

        # The stop is constructed after the trigger bar closes, so a one-hour
        # bar completing exactly at decision_time is available and causal.
        while (
            atr_index + 1 < len(atr_timeline)
            and atr_timeline[atr_index + 1][0] <= decision_time
        ):
            atr_index += 1
            latest_atr_timestamp, latest_atr = atr_timeline[atr_index]

        if _parse(next_bar.timestamp) != decision_time or latest_atr is None:
            continue

        matches = [
            zone
            for zone in live.values()
            if zone.active
            and (not params.one_signal_per_zone or zone.zone_id not in used_zone_ids)
            and _reaction_matches(zone, previous, bar, params)
        ]
        if not matches:
            continue

        # Prefer the strongest evidence, then the narrowest structure, then the
        # oldest deterministic identifier if overlapping zones react together.
        matches.sort(
            key=lambda zone: (
                -zone.current_score,
                -zone.qualification_score,
                zone.upper - zone.lower,
                zone.zone_id,
            )
        )
        selected = matches[0]
        if params.one_signal_per_zone:
            # All overlapping zones touched by this same reaction are consumed;
            # this prevents the same price response being counted repeatedly.
            used_zone_ids.update(zone.zone_id for zone in matches)

        stop_buffer = params.stop_buffer_one_hour_atr * latest_atr
        side = "long" if selected.side == "demand" else "short"
        stop = (
            selected.lower - stop_buffer
            if side == "long"
            else selected.upper + stop_buffer
        )
        signals.append(
            {
                "decision_timestamp": _format(decision_time),
                "entry_timestamp": next_bar.timestamp,
                "side": side,
                "entry_reference": next_bar.open,
                "jaw": stop,
                "stop_reference": stop,
                "zone_id": selected.zone_id,
                "zone_side": selected.side,
                "zone_lower": selected.lower,
                "zone_upper": selected.upper,
                "zone_status": selected.status,
                "qualified_score": selected.qualification_score,
                "current_score": selected.current_score,
                "trigger_timestamp": bar.timestamp,
                "trigger_open": bar.open,
                "trigger_high": bar.high,
                "trigger_low": bar.low,
                "trigger_close": bar.close,
                "one_hour_atr": latest_atr,
                "one_hour_atr_timestamp": _format(latest_atr_timestamp),
                "stop_buffer": stop_buffer,
                "reward_to_risk": 1.0,
            }
        )
    return signals


def candidate_signals_v1(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    execution_params: Strategy04ExecutionParameters = Strategy04ExecutionParameters(),
    indicator_params: Strategy04IndicatorParameters | None = None,
) -> Strategy04SignalResult:
    """Build the locked one-hour v0.3 zones and causal 15-minute signals."""

    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    indicator = build_one_hour_indicator(
        hours,
        indicator_params or strategy_04_v0_3_parameters(),
    )
    signals = signals_from_zone_events(
        fifteen,
        hours,
        indicator.events,
        execution_params,
    )
    return Strategy04SignalResult(signals=signals, indicator=indicator)

