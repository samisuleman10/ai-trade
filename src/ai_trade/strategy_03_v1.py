"""Strategy 03 v1: single-timeframe Alligator mouth-opening entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr


@dataclass(frozen=True)
class Strategy03V1Parameters:
    stop_atr_period: int = 14
    stop_atr_multiple: float = 0.10
    minimum_tick: float = 0.01

    def __post_init__(self) -> None:
        if self.stop_atr_period < 1 or self.stop_atr_multiple < 0 or self.minimum_tick <= 0:
            raise ValueError("invalid Strategy 03 stop-buffer parameters")


def _parsed(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def candidate_signals(
    bars: Iterable[OHLCVBar],
    *,
    interval_minutes: int,
    params: Strategy03V1Parameters = Strategy03V1Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Signal only on the first completed bar of a new open-mouth state.

    A long transition is ``not bullish_open -> bullish_open``; a short
    transition is the equivalent bearish state. Entry is the next immediate
    bar open, preventing current-bar look-ahead.
    """
    rows = list(bars)
    points = alligator_points(rows, alligator_params)
    volatility = atr(rows, params.stop_atr_period)
    signals: list[dict[str, object]] = []

    for index in range(1, len(rows) - 1):
        point, previous = points[index], points[index - 1]
        if point.jaw is None or volatility[index] is None:
            continue
        decision = _parsed(rows[index].timestamp) + timedelta(minutes=interval_minutes)
        next_bar = rows[index + 1]
        if _parsed(next_bar.timestamp) != decision:
            continue
        buffer = max(params.minimum_tick, params.stop_atr_multiple * float(volatility[index]))

        if point.bullish_open and not previous.bullish_open:
            stop = float(point.jaw) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signals.append({
                    "decision_timestamp": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "entry_timestamp": next_bar.timestamp,
                    "side": "long", "entry_reference": next_bar.open,
                    "jaw": point.jaw, "stop_reference": stop,
                    "target_reference": next_bar.open + risk, "risk_per_unit": risk,
                    "execution_timeframe_minutes": interval_minutes,
                })

        if point.bearish_open and not previous.bearish_open:
            stop = float(point.jaw) + buffer
            risk = stop - next_bar.open
            if risk > 0:
                signals.append({
                    "decision_timestamp": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "entry_timestamp": next_bar.timestamp,
                    "side": "short", "entry_reference": next_bar.open,
                    "jaw": point.jaw, "stop_reference": stop,
                    "target_reference": next_bar.open - risk, "risk_per_unit": risk,
                    "execution_timeframe_minutes": interval_minutes,
                })
    return signals
