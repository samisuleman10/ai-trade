"""Canonical Strategy 02 v1: Alligator reversal with structure-only stops.

RSI and RSI divergence are intentionally absent. The Cambist reference is used
only as a visual model for confirmed support and resistance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr


@dataclass(frozen=True)
class Strategy02Parameters:
    pivot_left: int = 5
    pivot_right: int = 3
    stop_atr_period: int = 14
    stop_atr_multiple: float = 0.10
    minimum_tick: float = 0.01
    trigger_with_heikin_ashi: bool = True

    def __post_init__(self) -> None:
        if self.pivot_left < 1 or self.pivot_right < 1:
            raise ValueError("pivot_left and pivot_right must be positive")
        if self.stop_atr_period < 1 or self.stop_atr_multiple < 0 or self.minimum_tick <= 0:
            raise ValueError("invalid stop-buffer parameters")


@dataclass(frozen=True)
class StructurePoint:
    timestamp: str
    ha_close: float
    support: Optional[float]
    resistance: Optional[float]
    support_pivot_timestamp: Optional[str]
    resistance_pivot_timestamp: Optional[str]
    support_confirmed_timestamp: Optional[str]
    resistance_confirmed_timestamp: Optional[str]
    new_support: bool
    new_resistance: bool


def _heikin_ashi(bars: list[OHLCVBar]) -> list[tuple[float, float, float, float]]:
    output: list[tuple[float, float, float, float]] = []
    previous_open: Optional[float] = None
    previous_close: Optional[float] = None
    for bar in bars:
        close = (bar.open + bar.high + bar.low + bar.close) / 4
        opening = (bar.open + bar.close) / 2 if previous_open is None else (previous_open + previous_close) / 2
        output.append((opening, max(bar.high, opening, close), min(bar.low, opening, close), close))
        previous_open, previous_close = opening, close
    return output


def _unique_pivot(values: list[float], candidate: int, left: int, right: int, *, low: bool) -> bool:
    window = values[candidate - left : candidate + right + 1]
    extreme = min(window) if low else max(window)
    return values[candidate] == extreme and window.count(extreme) == 1


def structure_points(
    bars: Iterable[OHLCVBar], params: Strategy02Parameters = Strategy02Parameters()
) -> list[StructurePoint]:
    """Return confirmed HA swing support/resistance without lookahead."""
    rows = list(bars)
    ha = _heikin_ashi(rows)
    highs = [item[1] for item in ha]
    lows = [item[2] for item in ha]
    support = resistance = None
    support_pivot = resistance_pivot = None
    support_confirmed = resistance_confirmed = None
    output: list[StructurePoint] = []

    for confirmation_index, bar in enumerate(rows):
        candidate = confirmation_index - params.pivot_right
        new_support = new_resistance = False
        if candidate >= params.pivot_left:
            if _unique_pivot(lows, candidate, params.pivot_left, params.pivot_right, low=True):
                support = lows[candidate]
                support_pivot = rows[candidate].timestamp
                support_confirmed = bar.timestamp
                new_support = True
            if _unique_pivot(highs, candidate, params.pivot_left, params.pivot_right, low=False):
                resistance = highs[candidate]
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
    params: Strategy02Parameters = Strategy02Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
    *,
    interval_minutes: int = 15,
) -> list[dict[str, object]]:
    """Return next-bar Scenario 2 candidates with structure-based stops."""
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
        buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)

        if point.bearish_open and prior_close <= prior.jaw and current_close > point.jaw and level.support is not None:
            stop = float(level.support) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signals.append(_signal("long", decision_time, next_bar, point.jaw, level, stop, risk))

        if point.bullish_open and prior_close >= prior.jaw and current_close < point.jaw and level.resistance is not None:
            stop = float(level.resistance) + buffer
            risk = stop - next_bar.open
            if risk > 0:
                signals.append(_signal("short", decision_time, next_bar, point.jaw, level, stop, risk))
    return signals


def _signal(
    side: str,
    decision_time: datetime,
    next_bar: OHLCVBar,
    jaw: float,
    level: StructurePoint,
    stop: float,
    risk: float,
) -> dict[str, object]:
    long_side = side == "long"
    return {
        "decision_timestamp": decision_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_timestamp": next_bar.timestamp,
        "side": side,
        "entry_reference": next_bar.open,
        "jaw": jaw,
        "structure_level": level.support if long_side else level.resistance,
        "structure_pivot_timestamp": (
            level.support_pivot_timestamp if long_side else level.resistance_pivot_timestamp
        ),
        "structure_confirmed_timestamp": (
            level.support_confirmed_timestamp if long_side else level.resistance_confirmed_timestamp
        ),
        "stop_reference": stop,
        "target_reference": next_bar.open + risk if long_side else next_bar.open - risk,
        "risk_per_unit": risk,
    }
