"""Strategy 04 v1.2: v1.1 plus two independent rejection filters.

Filter A rejects a reaction whose trigger close sits too far from its own
stop, measured in zone widths. Filter B rejects a reaction whose direction
opposes the latest completed one-hour candle. Both default to off; with both
off this module must reproduce v1.1 signal-for-signal (the ablation base).
A rejected reaction does not consume its zone: the filters run inside zone
matching, before selection and before used-zone marking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import atr
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    ZoneEvent,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.strategy_04_v1 import (
    Strategy04SignalResult,
    _TimelineZone,
    _apply_event,
    _bar_close,
    _format,
    _parse,
)
from ai_trade.strategy_04_v1_1 import (
    Strategy04V11ExecutionParameters,
    _reaction_matches_v1_1,
    long_zone_penetration_fraction,
)


@dataclass(frozen=True)
class Strategy04V12ExecutionParameters(Strategy04V11ExecutionParameters):
    """Version 1.2 adds two independently switchable rejection filters."""

    enable_filter_a: bool = False
    enable_filter_b: bool = False
    max_risk_zone_ratio: float = 2.5

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_risk_zone_ratio <= 0:
            raise ValueError("Risk-to-zone-width ratio must be positive")


def _hourly_atr_bar_timeline(
    bars: list[OHLCVBar], period: int, interval_minutes: int
) -> list[tuple[datetime, float, float, float]]:
    """v1's ATR timeline, additionally carrying the source bar's open/close.

    Filter B reads the direction of the exact bar the stop buffer already
    uses, so both must come from one timeline or they could diverge.
    """
    values = atr(bars, period)
    return [
        (_bar_close(bar, interval_minutes), float(value), bar.open, bar.close)
        for bar, value in zip(bars, values)
        if value is not None and value > 0
    ]


def risk_zone_ratio(zone: _TimelineZone, trigger_close: float, stop: float) -> float:
    """Return Filter A's decision value: risk distance in zone widths."""
    width = zone.upper - zone.lower
    if width <= 0:
        return float("inf")
    return abs(trigger_close - stop) / width


def _direction_agrees(side: str, reference_open: float, reference_close: float) -> bool:
    """Filter B agreement; doji bars (close == open) permit both directions."""
    if side == "long":
        return reference_close >= reference_open
    return reference_close <= reference_open


def signals_from_zone_events_v1_2(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    events: Iterable[ZoneEvent],
    params: Strategy04V12ExecutionParameters = Strategy04V12ExecutionParameters(),
) -> list[dict[str, object]]:
    """Create causal v1.2 signals; rejected reactions never consume zones."""

    entries = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    if len(entries) < 3 or not hours:
        return []

    ordered_events = sorted(list(events), key=lambda event: _parse(event.timestamp))
    atr_timeline = _hourly_atr_bar_timeline(
        hours, params.one_hour_atr_period, params.one_hour_interval_minutes
    )
    live: dict[int, _TimelineZone] = {}
    used_zone_ids: set[int] = set()
    event_index = 0
    atr_index = -1
    latest_atr: Optional[float] = None
    latest_atr_timestamp: Optional[datetime] = None
    latest_reference_open: Optional[float] = None
    latest_reference_close: Optional[float] = None
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
            (
                latest_atr_timestamp,
                latest_atr,
                latest_reference_open,
                latest_reference_close,
            ) = atr_timeline[atr_index]

        if _parse(next_bar.timestamp) != decision_time or latest_atr is None:
            continue

        stop_buffer = params.stop_buffer_one_hour_atr * latest_atr

        def _passes_filters(zone: _TimelineZone) -> bool:
            side = "long" if zone.side == "demand" else "short"
            stop = (
                zone.lower - stop_buffer if side == "long" else zone.upper + stop_buffer
            )
            if (
                params.enable_filter_a
                and risk_zone_ratio(zone, bar.close, stop) > params.max_risk_zone_ratio
            ):
                return False
            if params.enable_filter_b and not _direction_agrees(
                side, latest_reference_open, latest_reference_close
            ):
                return False
            return True

        # A reaction rejected by either filter is excluded here, so it is
        # neither selected nor marked used: the zone stays available.
        matches = [
            zone
            for zone in live.values()
            if zone.active
            and (not params.one_signal_per_zone or zone.zone_id not in used_zone_ids)
            and _reaction_matches_v1_1(zone, previous, bar, params)
            and _passes_filters(zone)
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

        side = "long" if selected.side == "demand" else "short"
        stop = (
            selected.lower - stop_buffer
            if side == "long"
            else selected.upper + stop_buffer
        )
        penetration = (
            long_zone_penetration_fraction(selected, bar) if side == "long" else None
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
                "risk_zone_ratio": risk_zone_ratio(selected, bar.close, stop),
                "one_hour_reference_open": latest_reference_open,
                "one_hour_reference_close": latest_reference_close,
            }
        )
    return signals


def candidate_signals_v1_2(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    execution_params: Strategy04V12ExecutionParameters = Strategy04V12ExecutionParameters(),
    indicator_params: Strategy04IndicatorParameters | None = None,
) -> Strategy04SignalResult:
    """Build v0.3 zones and the isolated Strategy 04 v1.2 signals."""

    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    indicator = build_one_hour_indicator(
        hours,
        indicator_params or strategy_04_v0_3_parameters(),
    )
    signals = signals_from_zone_events_v1_2(
        fifteen,
        hours,
        indicator.events,
        execution_params,
    )
    return Strategy04SignalResult(signals=signals, indicator=indicator)
