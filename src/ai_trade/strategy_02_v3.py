"""Strategy 02 v3: 4-hour trend confirmation and 1-hour reversal execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr
from ai_trade.strategy_02_v1 import _heikin_ashi, _signal
from ai_trade.strategy_02_v1_3 import Strategy02V13Parameters, hourly_structure_points


@dataclass(frozen=True)
class Strategy02V3Parameters(Strategy02V13Parameters):
    vix_threshold: float = 20.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.vix_threshold <= 0:
            raise ValueError("vix_threshold must be positive")


def _parsed(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _hourly_cross(ha_open: float, ha_close: float, jaw: float) -> str | None:
    if ha_open < jaw < ha_close:
        return "long"
    if ha_open > jaw > ha_close:
        return "short"
    return None


def candidate_signals(
    one_hour_bars: Iterable[OHLCVBar],
    four_hour_bars: Iterable[OHLCVBar],
    vix_fifteen_minute_bars: Iterable[OHLCVBar],
    params: Strategy02V3Parameters = Strategy02V3Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Return 1h reversal signals only when the completed 4h trend agrees.

    Long: 4h bullish open, 1h bearish open, then a completed 1h HA body crosses
    above its Jaw.  Short is the inverse.  Stops are beyond causal 1h structure.
    """
    entries, trend_bars, vix = list(one_hour_bars), list(four_hour_bars), list(vix_fifteen_minute_bars)
    a1h = alligator_points(entries, alligator_params)
    a4h = alligator_points(trend_bars, alligator_params)
    ha1h = _heikin_ashi(entries)
    structure1h = hourly_structure_points(entries, params)
    atr1h = atr(entries, params.stop_atr_period)
    entry_by_time = {bar.timestamp: index for index, bar in enumerate(entries)}
    completed_trends = [(_parsed(bar.timestamp) + timedelta(hours=4), point) for bar, point in zip(trend_bars, a4h)]
    completed_vix = [(_parsed(bar.timestamp) + timedelta(minutes=15), bar.close) for bar in vix]

    signals: list[dict[str, object]] = []
    for index, (bar, local_trend, level, volatility) in enumerate(zip(entries, a1h, structure1h, atr1h)):
        if local_trend.jaw is None or volatility is None:
            continue
        direction = _hourly_cross(ha1h[index][0], ha1h[index][3], local_trend.jaw)
        if direction is None:
            continue
        decision = _parsed(bar.timestamp) + timedelta(hours=1)
        entry_index = entry_by_time.get(decision.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if entry_index is None:
            continue
        available_trends = [item for item in completed_trends if item[0] <= decision]
        available_vix = [item for item in completed_vix if item[0] <= decision]
        if not available_trends or not available_vix:
            continue
        _, higher_trend = available_trends[-1]
        vix_time, vix_close = available_vix[-1]
        if vix_close >= params.vix_threshold:
            continue

        # Higher timeframe direction, local pullback direction, then local reversal.
        if direction == "long" and not (higher_trend.bullish_open and local_trend.bearish_open):
            continue
        if direction == "short" and not (higher_trend.bearish_open and local_trend.bullish_open):
            continue

        entry_bar = entries[entry_index]
        buffer = max(params.minimum_tick, params.stop_atr_multiple * volatility)
        if direction == "long" and level.support is not None:
            stop = float(level.support) - buffer
            risk = entry_bar.open - stop
            if risk > 0:
                signal = _signal("long", decision, entry_bar, local_trend.jaw, level, stop, risk)
                signal.update({
                    "trend_timeframe": "4h", "confirmation_timeframe": "1h",
                    "structure_timeframe": "1h", "execution_timeframe": "1h",
                    "vix_close": vix_close, "vix_timestamp": vix_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "vix_threshold": params.vix_threshold,
                })
                signals.append(signal)
        if direction == "short" and level.resistance is not None:
            stop = float(level.resistance) + buffer
            risk = stop - entry_bar.open
            if risk > 0:
                signal = _signal("short", decision, entry_bar, local_trend.jaw, level, stop, risk)
                signal.update({
                    "trend_timeframe": "4h", "confirmation_timeframe": "1h",
                    "structure_timeframe": "1h", "execution_timeframe": "1h",
                    "vix_close": vix_close, "vix_timestamp": vix_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "vix_threshold": params.vix_threshold,
                })
                signals.append(signal)
    return signals
