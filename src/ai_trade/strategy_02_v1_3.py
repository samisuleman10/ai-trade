"""Strategy 02 v1.3: 1-hour ZigZag structure, 15-minute execution.

The higher timeframe owns support/resistance and trend context. The lower
timeframe can only trigger after the relevant 1-hour bar has completed, which
prevents look-ahead during historical tests and live evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import StructurePoint, _heikin_ashi, _signal
from ai_trade.strategy_02_v1_1 import Strategy02V11Parameters


@dataclass(frozen=True)
class Strategy02V13Parameters(Strategy02V11Parameters):
    """Course ZigZag defaults plus the existing stop-buffer controls."""

    zigzag_depth: int = 18
    zigzag_deviation: int = 5
    zigzag_backstep: int = 3

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.zigzag_depth < 2 or self.zigzag_deviation < 1 or self.zigzag_backstep < 1:
            raise ValueError("ZigZag depth, deviation, and backstep must be positive")
        if self.zigzag_backstep >= self.zigzag_depth:
            raise ValueError("ZigZag backstep must be smaller than depth")


def _confirmed_extreme(
    values: list[float], candidate: int, *, depth: int, backstep: int, deviation: float, low: bool
) -> bool:
    """Confirm a meaningful swing rather than treating one wick as structure."""
    start = max(0, candidate - depth + 1)
    end = candidate + backstep + 1
    window = values[start:end]
    if len(window) < depth + backstep:
        return False
    extreme = min(window) if low else max(window)
    if values[candidate] != extreme:
        return False
    # Equal extreme clusters resolve to their final occurrence.
    if candidate != start + max(i for i, value in enumerate(window) if value == extreme):
        return False
    opposite = max(window) if low else min(window)
    return (opposite - extreme if low else extreme - opposite) >= deviation


def hourly_structure_points(
    hourly_bars: Iterable[OHLCVBar], params: Strategy02V13Parameters = Strategy02V13Parameters()
) -> list[StructurePoint]:
    """Build causal 1-hour ZigZag support/resistance with wick-safe dots."""
    rows = list(hourly_bars)
    ha = _heikin_ashi(rows)
    highs, lows = [row[1] for row in ha], [row[2] for row in ha]
    deviation = params.zigzag_deviation * params.minimum_tick
    offset = params.structure_offset_ticks * params.minimum_tick
    support = resistance = None
    support_pivot = resistance_pivot = None
    support_confirmed = resistance_confirmed = None
    output: list[StructurePoint] = []

    for confirmation_index, bar in enumerate(rows):
        # Broken higher-timeframe levels disappear on the completed breaking bar.
        if support is not None and lows[confirmation_index] <= support:
            support = support_pivot = support_confirmed = None
        if resistance is not None and highs[confirmation_index] >= resistance:
            resistance = resistance_pivot = resistance_confirmed = None

        candidate = confirmation_index - params.zigzag_backstep
        new_support = new_resistance = False
        if candidate >= 0:
            if _confirmed_extreme(lows, candidate, depth=params.zigzag_depth,
                                  backstep=params.zigzag_backstep, deviation=deviation, low=True):
                level = lows[candidate] - offset
                if all(value > level for value in lows[candidate + 1:confirmation_index + 1]):
                    support, support_pivot, support_confirmed = level, rows[candidate].timestamp, bar.timestamp
                    new_support = True
            if _confirmed_extreme(highs, candidate, depth=params.zigzag_depth,
                                  backstep=params.zigzag_backstep, deviation=deviation, low=False):
                level = highs[candidate] + offset
                if all(value < level for value in highs[candidate + 1:confirmation_index + 1]):
                    resistance, resistance_pivot, resistance_confirmed = level, rows[candidate].timestamp, bar.timestamp
                    new_resistance = True

        output.append(StructurePoint(
            timestamp=bar.timestamp, ha_close=ha[confirmation_index][3], support=support,
            resistance=resistance, support_pivot_timestamp=support_pivot,
            resistance_pivot_timestamp=resistance_pivot,
            support_confirmed_timestamp=support_confirmed,
            resistance_confirmed_timestamp=resistance_confirmed,
            new_support=new_support, new_resistance=new_resistance,
        ))
    return output


def candidate_signals(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    params: Strategy02V13Parameters = Strategy02V13Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Use completed 1-hour context and execute a Jaw cross on 15 minutes."""
    entries, hourly = list(fifteen_minute_bars), list(one_hour_bars)
    entry_alligator = alligator_points(entries, alligator_params)
    hourly_alligator = alligator_points(hourly, alligator_params)
    hourly_structure = hourly_structure_points(hourly, params)
    hourly_atr = atr(hourly, params.stop_atr_period)

    def parsed(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    completed = [(parsed(bar.timestamp) + timedelta(hours=1), a, s, v)
                 for bar, a, s, v in zip(hourly, hourly_alligator, hourly_structure, hourly_atr)]
    signals: list[dict[str, object]] = []
    ha15 = _heikin_ashi(entries)
    for index in range(1, len(entries) - 1):
        decision = parsed(entries[index].timestamp) + timedelta(minutes=15)
        next_bar = entries[index + 1]
        if parsed(next_bar.timestamp) != decision:
            continue
        available = [row for row in completed if row[0] <= decision]
        if not available:
            continue
        _, trend, level, volatility = available[-1]
        point, prior = entry_alligator[index], entry_alligator[index - 1]
        if point.jaw is None or prior.jaw is None or volatility is None:
            continue
        close = ha15[index][3] if params.trigger_with_heikin_ashi else entries[index].close
        previous_close = ha15[index - 1][3] if params.trigger_with_heikin_ashi else entries[index - 1].close
        buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)

        if trend.bearish_open and previous_close <= prior.jaw and close > point.jaw and level.support is not None:
            stop = float(level.support) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signal = _signal("long", decision, next_bar, point.jaw, level, stop, risk)
                signal.update({"structure_timeframe": "1h", "execution_timeframe": "15m"})
                signals.append(signal)
        if trend.bullish_open and previous_close >= prior.jaw and close < point.jaw and level.resistance is not None:
            stop = float(level.resistance) + buffer
            risk = stop - next_bar.open
            if risk > 0:
                signal = _signal("short", decision, next_bar, point.jaw, level, stop, risk)
                signal.update({"structure_timeframe": "1h", "execution_timeframe": "15m"})
                signals.append(signal)
    return signals
