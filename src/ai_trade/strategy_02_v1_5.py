"""Strategy 02 v1.5: 1h reversal confirmation, 15m alignment and structure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import _heikin_ashi, _signal
from ai_trade.strategy_02_v1_3 import Strategy02V13Parameters, hourly_structure_points


@dataclass(frozen=True)
class Strategy02V15Parameters(Strategy02V13Parameters):
    """Locked 1h/15m Scenario 2 parameters."""


def _hourly_cross(ha_open: float, ha_close: float, jaw: float) -> str | None:
    if ha_open < jaw < ha_close:
        return "long"
    if ha_open > jaw > ha_close:
        return "short"
    return None


def candidate_signals(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    params: Strategy02V15Parameters = Strategy02V15Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Return signals only when 1h reversal and 15m direction agree."""
    entries, hourly = list(fifteen_minute_bars), list(one_hour_bars)
    a15, a1h = alligator_points(entries, alligator_params), alligator_points(hourly, alligator_params)
    ha1h = _heikin_ashi(hourly)
    structure15 = hourly_structure_points(entries, params)
    atr15 = atr(entries, params.stop_atr_period)

    def parsed(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    entry_by_time = {bar.timestamp: index for index, bar in enumerate(entries)}
    signals: list[dict[str, object]] = []
    for hour_index, (hour, trend) in enumerate(zip(hourly, a1h)):
        if trend.jaw is None:
            continue
        direction = _hourly_cross(ha1h[hour_index][0], ha1h[hour_index][3], trend.jaw)
        if direction == "long" and not trend.bearish_open:
            continue
        if direction == "short" and not trend.bullish_open:
            continue
        if direction is None:
            continue

        decision = parsed(hour.timestamp) + timedelta(hours=1)
        entry_index = entry_by_time.get(decision.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if entry_index is None or entry_index == 0:
            continue
        confirmation_index = entry_index - 1
        alignment, level, volatility = a15[confirmation_index], structure15[confirmation_index], atr15[confirmation_index]
        if volatility is None:
            continue
        if direction == "long" and not alignment.bullish_open:
            continue
        if direction == "short" and not alignment.bearish_open:
            continue

        entry_bar = entries[entry_index]
        buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)
        if direction == "long" and level.support is not None:
            stop = float(level.support) - buffer
            risk = entry_bar.open - stop
            if risk > 0:
                signal = _signal("long", decision, entry_bar, trend.jaw, level, stop, risk)
                signal.update({"confirmation_timeframe": "1h", "alignment_timeframe": "15m",
                               "structure_timeframe": "15m", "execution_timeframe": "15m"})
                signals.append(signal)
        if direction == "short" and level.resistance is not None:
            stop = float(level.resistance) + buffer
            risk = stop - entry_bar.open
            if risk > 0:
                signal = _signal("short", decision, entry_bar, trend.jaw, level, stop, risk)
                signal.update({"confirmation_timeframe": "1h", "alignment_timeframe": "15m",
                               "structure_timeframe": "15m", "execution_timeframe": "15m"})
                signals.append(signal)
    return signals
