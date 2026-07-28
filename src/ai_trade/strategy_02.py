"""Strategy 02: causal Cambist-style structure and Alligator reversals.

The supplied ``.ex4`` file is compiled and cannot serve as source code. This is
an independent, documented implementation of the course idea. Pivots become
usable only after their right-side confirmation bars have completed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, atr


@dataclass(frozen=True)
class CambistParameters:
    rsi_period: int = 18
    pivot_left: int = 5
    pivot_right: int = 3
    stop_atr_period: int = 14
    stop_atr_multiple: float = 0.10
    minimum_tick: float = 0.01
    require_rsi_divergence: bool = False
    trigger_with_heikin_ashi: bool = True

    def __post_init__(self) -> None:
        if self.rsi_period < 2:
            raise ValueError("rsi_period must be at least 2")
        if self.pivot_left < 1 or self.pivot_right < 1:
            raise ValueError("pivot_left and pivot_right must be positive")
        if self.stop_atr_period < 1 or self.stop_atr_multiple < 0 or self.minimum_tick <= 0:
            raise ValueError("invalid stop-buffer parameters")


@dataclass(frozen=True)
class HeikinAshiBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class CambistPoint:
    """Everything knowable at one completed bar close."""

    timestamp: str
    ha_open: float
    ha_high: float
    ha_low: float
    ha_close: float
    rsi: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    support_pivot_timestamp: Optional[str]
    resistance_pivot_timestamp: Optional[str]
    support_confirmed_timestamp: Optional[str]
    resistance_confirmed_timestamp: Optional[str]
    support_has_bullish_divergence: bool
    resistance_has_bearish_divergence: bool
    new_support: bool
    new_resistance: bool


def heikin_ashi_bars(bars: Iterable[OHLCVBar]) -> list[HeikinAshiBar]:
    output: list[HeikinAshiBar] = []
    previous_open: Optional[float] = None
    previous_close: Optional[float] = None
    for bar in bars:
        close = (bar.open + bar.high + bar.low + bar.close) / 4
        opening = (bar.open + bar.close) / 2 if previous_open is None else (previous_open + previous_close) / 2
        output.append(
            HeikinAshiBar(
                timestamp=bar.timestamp,
                open=opening,
                high=max(bar.high, opening, close),
                low=min(bar.low, opening, close),
                close=close,
            )
        )
        previous_open, previous_close = opening, close
    return output


def rsi(values: Iterable[float], period: int = 18) -> list[Optional[float]]:
    """Wilder RSI with no value before a complete seed window."""
    rows = list(values)
    output: list[Optional[float]] = [None] * len(rows)
    if len(rows) <= period:
        return output
    gains = [max(rows[i] - rows[i - 1], 0.0) for i in range(1, len(rows))]
    losses = [max(rows[i - 1] - rows[i], 0.0) for i in range(1, len(rows))]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def calculate(gain: float, loss: float) -> float:
        if gain == 0 and loss == 0:
            return 50.0
        if loss == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    output[period] = calculate(average_gain, average_loss)
    for index in range(period + 1, len(rows)):
        delta_index = index - 1
        average_gain = (average_gain * (period - 1) + gains[delta_index]) / period
        average_loss = (average_loss * (period - 1) + losses[delta_index]) / period
        output[index] = calculate(average_gain, average_loss)
    return output


def _unique_pivot(values: list[float], candidate: int, left: int, right: int, *, low: bool) -> bool:
    window = values[candidate - left : candidate + right + 1]
    extreme = min(window) if low else max(window)
    return values[candidate] == extreme and window.count(extreme) == 1


def cambist_points(
    bars: Iterable[OHLCVBar], params: CambistParameters = CambistParameters()
) -> list[CambistPoint]:
    """Return causal HA structure levels and RSI-divergence metadata."""
    rows = list(bars)
    ha = heikin_ashi_bars(rows)
    rsi_values = rsi((bar.close for bar in ha), params.rsi_period)
    lows = [bar.low for bar in ha]
    highs = [bar.high for bar in ha]
    confirmed_lows: list[tuple[int, float, Optional[float]]] = []
    confirmed_highs: list[tuple[int, float, Optional[float]]] = []
    support = resistance = None
    support_pivot = resistance_pivot = None
    support_confirmed = resistance_confirmed = None
    support_divergence = resistance_divergence = False
    output: list[CambistPoint] = []

    for confirmation_index, current in enumerate(ha):
        candidate = confirmation_index - params.pivot_right
        new_support = new_resistance = False
        if candidate >= params.pivot_left:
            if _unique_pivot(lows, candidate, params.pivot_left, params.pivot_right, low=True):
                candidate_rsi = rsi_values[candidate]
                previous = confirmed_lows[-1] if confirmed_lows else None
                support_divergence = bool(
                    previous
                    and candidate_rsi is not None
                    and previous[2] is not None
                    and lows[candidate] < previous[1]
                    and candidate_rsi > previous[2]
                )
                confirmed_lows.append((candidate, lows[candidate], candidate_rsi))
                support = lows[candidate]
                support_pivot = ha[candidate].timestamp
                support_confirmed = current.timestamp
                new_support = True
            if _unique_pivot(highs, candidate, params.pivot_left, params.pivot_right, low=False):
                candidate_rsi = rsi_values[candidate]
                previous = confirmed_highs[-1] if confirmed_highs else None
                resistance_divergence = bool(
                    previous
                    and candidate_rsi is not None
                    and previous[2] is not None
                    and highs[candidate] > previous[1]
                    and candidate_rsi < previous[2]
                )
                confirmed_highs.append((candidate, highs[candidate], candidate_rsi))
                resistance = highs[candidate]
                resistance_pivot = ha[candidate].timestamp
                resistance_confirmed = current.timestamp
                new_resistance = True
        output.append(
            CambistPoint(
                timestamp=current.timestamp,
                ha_open=current.open,
                ha_high=current.high,
                ha_low=current.low,
                ha_close=current.close,
                rsi=rsi_values[confirmation_index],
                support=support,
                resistance=resistance,
                support_pivot_timestamp=support_pivot,
                resistance_pivot_timestamp=resistance_pivot,
                support_confirmed_timestamp=support_confirmed,
                resistance_confirmed_timestamp=resistance_confirmed,
                support_has_bullish_divergence=support_divergence,
                resistance_has_bearish_divergence=resistance_divergence,
                new_support=new_support,
                new_resistance=new_resistance,
            )
        )
    return output


def candidate_signals_scenario2(
    bars: Iterable[OHLCVBar],
    params: CambistParameters = CambistParameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
    *,
    interval_minutes: int = 15,
) -> list[dict[str, object]]:
    """Return preliminary next-bar Scenario 2 reversal signals.

    This signal layer intentionally excludes session, macro, higher-timeframe,
    RRMS, and execution permissions. Those remain separate decisions.
    """
    rows = list(bars)
    alligator = alligator_points(rows, alligator_params)
    structure = cambist_points(rows, params)
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

        long_ready = (
            point.bearish_open
            and prior_close <= prior.jaw
            and current_close > point.jaw
            and level.support is not None
            and (not params.require_rsi_divergence or level.support_has_bullish_divergence)
        )
        if long_ready:
            stop = float(level.support) - buffer
            risk = next_bar.open - stop
            if risk > 0:
                signals.append(_signal("long", decision_time, next_bar, point.jaw, level, stop, risk))

        short_ready = (
            point.bullish_open
            and prior_close >= prior.jaw
            and current_close < point.jaw
            and level.resistance is not None
            and (not params.require_rsi_divergence or level.resistance_has_bearish_divergence)
        )
        if short_ready:
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
    level: CambistPoint,
    stop: float,
    risk: float,
) -> dict[str, object]:
    support = side == "long"
    return {
        "decision_timestamp": decision_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entry_timestamp": next_bar.timestamp,
        "side": side,
        "entry_reference": next_bar.open,
        "jaw": jaw,
        "structure_level": level.support if support else level.resistance,
        "structure_pivot_timestamp": level.support_pivot_timestamp if support else level.resistance_pivot_timestamp,
        "structure_confirmed_timestamp": (
            level.support_confirmed_timestamp if support else level.resistance_confirmed_timestamp
        ),
        "rsi_divergence": (
            level.support_has_bullish_divergence if support else level.resistance_has_bearish_divergence
        ),
        "stop_reference": stop,
        "target_reference": next_bar.open + risk if support else next_bar.open - risk,
        "risk_per_unit": risk,
    }
