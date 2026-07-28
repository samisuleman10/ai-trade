"""Strategy 02 v1.1: structure dots outside wick clusters.

Support dots sit one or more ticks below the confirmed wick low. Resistance
dots sit above the confirmed wick high. Stops receive a second, independent ATR
buffer beyond those dots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import StructurePoint, Strategy02Parameters, _heikin_ashi, _signal


@dataclass(frozen=True)
class Strategy02V11Parameters(Strategy02Parameters):
    structure_offset_ticks: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.structure_offset_ticks < 1:
            raise ValueError("structure_offset_ticks must be positive")


def _plateau_pivot(values: list[float], candidate: int, left: int, right: int, *, low: bool) -> bool:
    """Confirm the final equal extreme in a wick cluster.

    Repeated equal lows/highs are common. Selecting the final occurrence keeps
    one causal level while ensuring the level uses the cluster's true extreme.
    """
    start = candidate - left
    window = values[start : candidate + right + 1]
    extreme = min(window) if low else max(window)
    if values[candidate] != extreme:
        return False
    last_extreme = start + max(index for index, value in enumerate(window) if value == extreme)
    return candidate == last_extreme


def structure_points(
    bars: Iterable[OHLCVBar], params: Strategy02V11Parameters = Strategy02V11Parameters()
) -> list[StructurePoint]:
    """Return confirmed support dots below wicks and resistance dots above."""
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
        candidate = confirmation_index - params.pivot_right
        new_support = new_resistance = False
        if candidate >= params.pivot_left:
            if _plateau_pivot(lows, candidate, params.pivot_left, params.pivot_right, low=True):
                support = lows[candidate] - dot_offset
                support_pivot = rows[candidate].timestamp
                support_confirmed = bar.timestamp
                new_support = True
            if _plateau_pivot(highs, candidate, params.pivot_left, params.pivot_right, low=False):
                resistance = highs[candidate] + dot_offset
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
    params: Strategy02V11Parameters = Strategy02V11Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
    *,
    interval_minutes: int = 15,
) -> list[dict[str, object]]:
    """Return Scenario 2 candidates with stops beyond the structure dots."""
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
