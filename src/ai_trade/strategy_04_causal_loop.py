"""Shared causal signal loop for Strategy 04 versions from v1.2 onward.

Every version before this module copied the ~130-line loop wholesale; a copy
per version means a fix per version. Here a version supplies only its
rejection logic (``reaction_filter``) and its extra output columns
(``extra_columns``). The rejection hook runs inside zone matching, before
selection and before used-zone marking, so a rejected reaction never
consumes its zone — the same non-consumption property the copied loops
guaranteed by construction.

v1.1 deliberately keeps its own copy: it is frozen and published, and its
committed results are the parity reference the v1.2 ablation base is
verified against.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, Optional, Tuple

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import atr
from ai_trade.strategy_04_indicator import ZoneEvent
from ai_trade.strategy_04_v1 import (
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
class ReactionContext:
    """Decision-time facts shared by rejection filters and column builders."""

    previous: OHLCVBar
    bar: OHLCVBar
    next_bar: OHLCVBar
    decision_time: datetime
    stop_buffer: float
    latest_atr: float
    latest_atr_timestamp: datetime
    reference_open: float
    reference_close: float

    def side_and_stop(self, zone: _TimelineZone) -> Tuple[str, float]:
        """One side/stop implementation for filters and emission alike.

        A filter that derived the stop itself could drift from the stop the
        emitted signal records; routing both through here makes that
        divergence impossible rather than merely unlikely.
        """
        side = "long" if zone.side == "demand" else "short"
        stop = (
            zone.lower - self.stop_buffer
            if side == "long"
            else zone.upper + self.stop_buffer
        )
        return side, stop


def _hourly_atr_bar_timeline(
    bars: list[OHLCVBar], period: int, interval_minutes: int
) -> list[tuple[datetime, float, float, float]]:
    """v1's ATR timeline, additionally carrying the source bar's open/close.

    Direction-style filters read the exact bar the stop buffer already uses,
    so both must come from one timeline or they could diverge. Versions that
    ignore the open/close are unaffected: the ``value is not None and
    value > 0`` predicate is unchanged from v1, so the same bars survive.
    """
    values = atr(bars, period)
    return [
        (_bar_close(bar, interval_minutes), float(value), bar.open, bar.close)
        for bar, value in zip(bars, values)
        if value is not None and value > 0
    ]


def signals_from_zone_events(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    events: Iterable[ZoneEvent],
    params: Strategy04V11ExecutionParameters,
    *,
    reaction_filter: Optional[
        Callable[[_TimelineZone, ReactionContext], bool]
    ] = None,
    extra_columns: Optional[
        Callable[[_TimelineZone, ReactionContext], Dict[str, object]]
    ] = None,
) -> list[dict[str, object]]:
    """Create causal signals; reactions rejected by the hook never consume zones."""

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
        context = ReactionContext(
            previous=previous,
            bar=bar,
            next_bar=next_bar,
            decision_time=decision_time,
            stop_buffer=stop_buffer,
            latest_atr=latest_atr,
            latest_atr_timestamp=latest_atr_timestamp,
            reference_open=latest_reference_open,
            reference_close=latest_reference_close,
        )

        # A reaction rejected by the hook is excluded here, so it is neither
        # selected nor marked used: the zone stays available for later bars.
        matches = [
            zone
            for zone in live.values()
            if zone.active
            and (not params.one_signal_per_zone or zone.zone_id not in used_zone_ids)
            and _reaction_matches_v1_1(zone, previous, bar, params)
            and (reaction_filter is None or reaction_filter(zone, context))
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

        side, stop = context.side_and_stop(selected)
        penetration = (
            long_zone_penetration_fraction(selected, bar) if side == "long" else None
        )
        signal: dict[str, object] = {
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
        if extra_columns is not None:
            # dict.update appends unseen keys in order, so a version's extra
            # columns land after the shared ones — the recorded CSV layout.
            signal.update(extra_columns(selected, context))
        signals.append(signal)
    return signals
