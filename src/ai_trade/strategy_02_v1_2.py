"""Strategy 02 v1.2: wick-safe, invalidated structure dots.

An active support/resistance dot series disappears as soon as a completed wick
crosses it. A new series starts only when a later pivot is causally confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import StructurePoint, _heikin_ashi, _signal
from ai_trade.strategy_02_v1_1 import Strategy02V11Parameters, _plateau_pivot


@dataclass(frozen=True)
class Strategy02V12Parameters(Strategy02V11Parameters):
    pass


def structure_points(
    bars: Iterable[OHLCVBar], params: Strategy02V12Parameters = Strategy02V12Parameters()
) -> list[StructurePoint]:
    """Return structure dots that never overlap or cross completed wicks."""
    rows = list(bars)
    ha = _heikin_ashi(rows)
    highs = [item[1] for item in ha]
    lows = [item[2] for item in ha]
    dot_offset = params.minimum_tick * params.structure_offset_ticks
    support = resistance = None
    support_pivot = resistance_pivot = None
    support_confirmed = resistance_confirmed = None
    output: list[StructurePoint] = []

    for confirmation_index, bar in enumerate(rows):
        # A broken level stops displaying on the breaking completed candle.
        if support is not None and lows[confirmation_index] <= support:
            support = support_pivot = support_confirmed = None
        if resistance is not None and highs[confirmation_index] >= resistance:
            resistance = resistance_pivot = resistance_confirmed = None

        candidate = confirmation_index - params.pivot_right
        new_support = new_resistance = False
        if candidate >= params.pivot_left:
            if _plateau_pivot(lows, candidate, params.pivot_left, params.pivot_right, low=True):
                candidate_level = lows[candidate] - dot_offset
                # Do not revive a historical level already broken before its
                # confirmation bar.
                post_pivot_lows = lows[candidate + 1 : confirmation_index + 1]
                if all(value > candidate_level for value in post_pivot_lows):
                    support = candidate_level
                    support_pivot = rows[candidate].timestamp
                    support_confirmed = bar.timestamp
                    new_support = True
            if _plateau_pivot(highs, candidate, params.pivot_left, params.pivot_right, low=False):
                candidate_level = highs[candidate] + dot_offset
                post_pivot_highs = highs[candidate + 1 : confirmation_index + 1]
                if all(value < candidate_level for value in post_pivot_highs):
                    resistance = candidate_level
                    resistance_pivot = rows[candidate].timestamp
                    resistance_confirmed = bar.timestamp
                    new_resistance = True
        output.append(
            StructurePoint(
                timestamp=bar.timestamp,
                ha_close=ha[confirmation_index][3],
                support=support,
                resistance=resistance,
                support_pivot_timestamp=support_pivot,
                resistance_pivot_timestamp=resistance_pivot,
                support_confirmed_timestamp=support_confirmed,
                resistance_confirmed_timestamp=resistance_confirmed,
                new_support=new_support,
                new_resistance=new_resistance,
            )
        )
    return output


def candidate_signals(
    bars: Iterable[OHLCVBar],
    params: Strategy02V12Parameters = Strategy02V12Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
    *,
    interval_minutes: int = 15,
) -> list[dict[str, object]]:
    """Return Scenario 2 signals only when unbroken structure exists."""
    rows = list(bars)
    alligator = alligator_points(rows, alligator_params)
    structure = structure_points(rows, params)
    atr_values = atr(rows, params.stop_atr_period)
    signals: list[dict[str, object]] = []

    def parsed(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    for index in range(1, len(rows) - 1):
        point, prior = alligator[index], alligator[index - 1]
        level = structure[index]
        volatility = atr_values[index]
        if point.jaw is None or prior.jaw is None or volatility is None:
            continue
        current_close = level.ha_close if params.trigger_with_heikin_ashi else rows[index].close
        prior_close = structure[index - 1].ha_close if params.trigger_with_heikin_ashi else rows[index - 1].close
        next_bar = rows[index + 1]
        decision_time = parsed(rows[index].timestamp) + timedelta(minutes=interval_minutes)
        if parsed(next_bar.timestamp) != decision_time:
            continue
        stop_buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)

        if point.bearish_open and prior_close <= prior.jaw and current_close > point.jaw and level.support is not None:
            stop = float(level.support) - stop_buffer
            risk = next_bar.open - stop
            if risk > 0:
                signals.append(_signal("long", decision_time, next_bar, point.jaw, level, stop, risk))

        if point.bullish_open and prior_close >= prior.jaw and current_close < point.jaw and level.resistance is not None:
            stop = float(level.resistance) + stop_buffer
            risk = stop - next_bar.open
            if risk > 0:
                signals.append(_signal("short", decision_time, next_bar, point.jaw, level, stop, risk))
    return signals
