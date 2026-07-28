"""Strategy 02 v1.4: full 15-minute Heikin-Ashi body break of Jaw."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import _heikin_ashi, _signal
from ai_trade.strategy_02_v1_3 import Strategy02V13Parameters, hourly_structure_points


@dataclass(frozen=True)
class Strategy02V14Parameters(Strategy02V13Parameters):
    """V1.3 settings with the clarified full-body entry rule."""


def candidate_signals(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    params: Strategy02V14Parameters = Strategy02V14Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Use completed 1-hour structure and full-body 15-minute Jaw breaks."""
    entries, hourly = list(fifteen_minute_bars), list(one_hour_bars)
    entry_alligator = alligator_points(entries, alligator_params)
    hourly_alligator = alligator_points(hourly, alligator_params)
    hourly_structure = hourly_structure_points(hourly, params)
    hourly_atr = atr(hourly, params.stop_atr_period)
    ha15 = _heikin_ashi(entries)

    def parsed(value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    completed = [(parsed(bar.timestamp) + timedelta(hours=1), a, s, v)
                 for bar, a, s, v in zip(hourly, hourly_alligator, hourly_structure, hourly_atr)]
    signals: list[dict[str, object]] = []
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
        current_open = ha15[index][0] if params.trigger_with_heikin_ashi else entries[index].open
        current_close = ha15[index][3] if params.trigger_with_heikin_ashi else entries[index].close
        previous_close = ha15[index - 1][3] if params.trigger_with_heikin_ashi else entries[index - 1].close
        buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)

        long_break = previous_close <= prior.jaw and min(current_open, current_close) > point.jaw
        if trend.bearish_open and long_break and level.support is not None:
            stop = float(level.support) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signal = _signal("long", decision, next_bar, point.jaw, level, stop, risk)
                signal.update({"structure_timeframe": "1h", "execution_timeframe": "15m",
                               "entry_rule": "full_heikin_ashi_body_above_jaw"})
                signals.append(signal)

        short_break = previous_close >= prior.jaw and max(current_open, current_close) < point.jaw
        if trend.bullish_open and short_break and level.resistance is not None:
            stop = float(level.resistance) + buffer
            risk = stop - next_bar.open
            if risk > 0:
                signal = _signal("short", decision, next_bar, point.jaw, level, stop, risk)
                signal.update({"structure_timeframe": "1h", "execution_timeframe": "15m",
                               "entry_rule": "full_heikin_ashi_body_below_jaw"})
                signals.append(signal)
    return signals
