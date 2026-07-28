"""Strategy 04 v1.1: v1 plus a shallow long demand-zone reaction filter.

Only long entries change. A long trigger may penetrate no more than 25% of
the demand-zone width. Short entries and all remaining v1 rules are retained.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    ZoneEvent,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.strategy_04_v1 import (
    Strategy04ExecutionParameters,
    Strategy04SignalResult,
    _TimelineZone,
    _apply_event,
    _bar_close,
    _format,
    _hourly_atr_timeline,
    _parse,
    _reaction_matches,
)


@dataclass(frozen=True)
class Strategy04V11ExecutionParameters(Strategy04ExecutionParameters):
    """Version 1.1 changes only the permitted long-zone penetration."""

    max_long_zone_penetration_fraction: float = 0.25

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 0 <= self.max_long_zone_penetration_fraction <= 1:
            raise ValueError("Long penetration fraction must be between 0 and 1")


def long_zone_penetration_fraction(zone: _TimelineZone, bar: OHLCVBar) -> float:
    """Return how far the trigger low travelled down through demand."""

    width = zone.upper - zone.lower
    if width <= 0:
        return float("inf")
    return max(0.0, (zone.upper - bar.low) / width)


def _reaction_matches_v1_1(
    zone: _TimelineZone,
    previous: OHLCVBar,
    bar: OHLCVBar,
    params: Strategy04V11ExecutionParameters,
) -> bool:
    if not _reaction_matches(zone, previous, bar, params):
        return False
    if zone.side != "demand":
        return True
    return (
        long_zone_penetration_fraction(zone, bar)
        <= params.max_long_zone_penetration_fraction
    )


def signals_from_zone_events_v1_1(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    events: Iterable[ZoneEvent],
    params: Strategy04V11ExecutionParameters = Strategy04V11ExecutionParameters(),
) -> list[dict[str, object]]:
    """Create causal v1.1 signals without consuming rejected deep reactions."""

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

        while (
            event_index < len(ordered_events)
            and _parse(ordered_events[event_index].timestamp) <= bar_start
        ):
            _apply_event(live, ordered_events[event_index])
            event_index += 1

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
            and _reaction_matches_v1_1(zone, previous, bar, params)
        ]
        if not matches:
            continue

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
            used_zone_ids.update(zone.zone_id for zone in matches)

        stop_buffer = params.stop_buffer_one_hour_atr * latest_atr
        side = "long" if selected.side == "demand" else "short"
        stop = (
            selected.lower - stop_buffer
            if side == "long"
            else selected.upper + stop_buffer
        )
        penetration = (
            long_zone_penetration_fraction(selected, bar)
            if side == "long"
            else None
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
                "long_zone_penetration_fraction": penetration,
                "reward_to_risk": 1.0,
            }
        )
    return signals


def candidate_signals_v1_1(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    execution_params: Strategy04V11ExecutionParameters = Strategy04V11ExecutionParameters(),
    indicator_params: Strategy04IndicatorParameters | None = None,
) -> Strategy04SignalResult:
    """Build v0.3 zones and the isolated Strategy 04 v1.1 signals."""

    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    indicator = build_one_hour_indicator(
        hours,
        indicator_params or strategy_04_v0_3_parameters(),
    )
    signals = signals_from_zone_events_v1_1(
        fifteen,
        hours,
        indicator.events,
        execution_params,
    )
    return Strategy04SignalResult(signals=signals, indicator=indicator)
