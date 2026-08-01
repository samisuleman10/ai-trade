"""Strategy 04 v1.2: v1.1 plus two independent rejection filters.

Filter A rejects a reaction whose trigger close sits too far from its own
stop, measured in zone widths. Filter B rejects a reaction whose direction
opposes the latest completed one-hour candle. Both default to off; with both
off this module must reproduce v1.1 signal-for-signal (the ablation base).
A rejected reaction does not consume its zone: the filters run inside zone
matching, before selection and before used-zone marking.

The causal loop itself lives in ``strategy_04_causal_loop``; this module
contributes only the two filters and the three v1.2 audit columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_causal_loop import (
    ReactionContext,
    signals_from_zone_events,
)
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    ZoneEvent,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.strategy_04_v1 import Strategy04SignalResult, _TimelineZone
from ai_trade.strategy_04_v1_1 import Strategy04V11ExecutionParameters


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

    def _passes_filters(zone: _TimelineZone, context: ReactionContext) -> bool:
        side, stop = context.side_and_stop(zone)
        if (
            params.enable_filter_a
            and risk_zone_ratio(zone, context.bar.close, stop)
            > params.max_risk_zone_ratio
        ):
            return False
        if params.enable_filter_b and not _direction_agrees(
            side, context.reference_open, context.reference_close
        ):
            return False
        return True

    def _audit_columns(selected: _TimelineZone, context: ReactionContext) -> dict[str, object]:
        # Recorded even with both filters off, so the independent audit can
        # re-derive the filter decisions from the CSV alone.
        _, stop = context.side_and_stop(selected)
        return {
            "risk_zone_ratio": risk_zone_ratio(selected, context.bar.close, stop),
            "one_hour_reference_open": context.reference_open,
            "one_hour_reference_close": context.reference_close,
        }

    return signals_from_zone_events(
        fifteen_minute_bars,
        one_hour_bars,
        events,
        params,
        reaction_filter=_passes_filters,
        extra_columns=_audit_columns,
    )


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
