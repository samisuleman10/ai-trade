"""Strategy 03 v1 adapter for IBKR regular-session 4-hour bars."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_03_v1 import Strategy03V1Parameters


def _parsed(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def candidate_signals(
    bars: Iterable[OHLCVBar],
    params: Strategy03V1Parameters = Strategy03V1Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Use the observed same-session next bar as the completed-bar boundary.

    IBKR RTH 4-hour bars have a shortened opening segment. A signal on that
    completed segment may enter at the next segment's open. The final segment
    of a session cannot enter after an overnight gap and is therefore skipped.
    """
    rows = list(bars)
    points = alligator_points(rows, alligator_params)
    volatility = atr(rows, params.stop_atr_period)
    eastern = ZoneInfo("America/New_York")
    signals: list[dict[str, object]] = []

    for index in range(1, len(rows) - 1):
        point, previous = points[index], points[index - 1]
        if point.jaw is None or volatility[index] is None:
            continue
        current_start = _parsed(rows[index].timestamp)
        next_bar = rows[index + 1]
        next_start = _parsed(next_bar.timestamp)
        if current_start.astimezone(eastern).date() != next_start.astimezone(eastern).date():
            continue
        decision = next_start
        buffer = max(params.minimum_tick, params.stop_atr_multiple * float(volatility[index]))

        if point.bullish_open and not previous.bullish_open:
            stop = float(point.jaw) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signals.append({
                    "decision_timestamp": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "entry_timestamp": next_bar.timestamp, "side": "long",
                    "entry_reference": next_bar.open, "jaw": point.jaw,
                    "stop_reference": stop, "target_reference": next_bar.open + risk,
                    "risk_per_unit": risk, "execution_timeframe_minutes": 240,
                })
        if point.bearish_open and not previous.bearish_open:
            stop = float(point.jaw) + buffer
            risk = stop - next_bar.open
            if risk > 0:
                signals.append({
                    "decision_timestamp": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "entry_timestamp": next_bar.timestamp, "side": "short",
                    "entry_reference": next_bar.open, "jaw": point.jaw,
                    "stop_reference": stop, "target_reference": next_bar.open - risk,
                    "risk_per_unit": risk, "execution_timeframe_minutes": 240,
                })
    return signals
