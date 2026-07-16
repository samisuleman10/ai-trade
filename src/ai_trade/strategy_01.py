"""No-lookahead diagnostics for Strategy 01 (Alligator + Heikin Ashi)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from ai_trade.market_data import OHLCVBar


@dataclass(frozen=True)
class Strategy01Parameters:
    slope_lookback_bars: int = 3
    minimum_line_separation_percent: float = 0.0002
    require_widening_separation: bool = True


@dataclass(frozen=True)
class AlligatorPoint:
    timestamp: str
    jaw: Optional[float]
    teeth: Optional[float]
    lips: Optional[float]
    ha_open: float
    ha_close: float
    bullish_open: bool
    bearish_open: bool


def load_ohlcv_csv(path: Path) -> list[OHLCVBar]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            OHLCVBar(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in csv.DictReader(handle)
        ]


def smma(values: Iterable[float], period: int) -> list[Optional[float]]:
    """Smoothed moving average with no values before a complete seed window."""
    values = list(values)
    output: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return output
    previous = sum(values[:period]) / period
    output[period - 1] = previous
    for index in range(period, len(values)):
        previous = (previous * (period - 1) + values[index]) / period
        output[index] = previous
    return output


def heikin_ashi(bars: Iterable[OHLCVBar]) -> list[tuple[float, float]]:
    """Return (HA open, HA close) for each bar using only past/current OHLC."""
    output: list[tuple[float, float]] = []
    previous_open: Optional[float] = None
    previous_close: Optional[float] = None
    for bar in bars:
        close = (bar.open + bar.high + bar.low + bar.close) / 4
        opening = (bar.open + bar.close) / 2 if previous_open is None else (previous_open + previous_close) / 2
        output.append((opening, close))
        previous_open, previous_close = opening, close
    return output


def _displayed(raw: list[Optional[float]], offset: int) -> list[Optional[float]]:
    """Return values as displayed at each bar, using only earlier raw values."""
    return [None if index < offset else raw[index - offset] for index in range(len(raw))]


def alligator_points(bars: Iterable[OHLCVBar], params: Strategy01Parameters = Strategy01Parameters()) -> list[AlligatorPoint]:
    """Compute display-aligned Alligator values and measurable open-mouth states."""
    rows = list(bars)
    median = [(bar.high + bar.low) / 2 for bar in rows]
    jaw = _displayed(smma(median, 13), 8)
    teeth = _displayed(smma(median, 8), 5)
    lips = _displayed(smma(median, 5), 3)
    ha = heikin_ashi(rows)
    output: list[AlligatorPoint] = []

    for index, bar in enumerate(rows):
        current_jaw, current_teeth, current_lips = jaw[index], teeth[index], lips[index]
        bullish = bearish = False
        past_index = index - params.slope_lookback_bars
        if (
            past_index >= 0
            and None not in (current_jaw, current_teeth, current_lips, jaw[past_index], teeth[past_index], lips[past_index])
        ):
            assert current_jaw is not None and current_teeth is not None and current_lips is not None
            prior_jaw, prior_teeth, prior_lips = jaw[past_index], teeth[past_index], lips[past_index]
            assert prior_jaw is not None and prior_teeth is not None and prior_lips is not None
            spread = abs(current_lips - current_jaw) / bar.close
            prior_spread = abs(prior_lips - prior_jaw) / rows[past_index].close
            wide_enough = spread >= params.minimum_line_separation_percent
            widening = spread > prior_spread if params.require_widening_separation else True
            bullish = (
                current_lips > current_teeth > current_jaw
                and current_lips > prior_lips
                and current_teeth > prior_teeth
                and current_jaw > prior_jaw
                and wide_enough
                and widening
            )
            bearish = (
                current_lips < current_teeth < current_jaw
                and current_lips < prior_lips
                and current_teeth < prior_teeth
                and current_jaw < prior_jaw
                and wide_enough
                and widening
            )
        output.append(
            AlligatorPoint(
                timestamp=bar.timestamp,
                jaw=current_jaw,
                teeth=current_teeth,
                lips=current_lips,
                ha_open=ha[index][0],
                ha_close=ha[index][1],
                bullish_open=bullish,
                bearish_open=bearish,
            )
        )
    return output


def candidate_signals(
    entry_bars: Iterable[OHLCVBar],
    trend_bars: Iterable[OHLCVBar],
    params: Strategy01Parameters = Strategy01Parameters(),
    *,
    entry_interval_minutes: int = 15,
    trend_interval_minutes: int = 60,
    minimum_decision_close_time: Optional[tuple[int, int]] = (10, 45),
    infer_trend_close_from_session_boundaries: bool = False,
    infer_shortened_trend_bars: bool = False,
) -> list[dict[str, object]]:
    """Return state transitions where completed 1h and 15m conditions agree.

    Timestamp alignment uses the latest completed trend bar at or before the
    entry-timeframe decision bar. Returned records are diagnostics, not orders.
    Defaults preserve the original 15-minute / 1-hour version of Strategy 01.
    """
    entries = list(entry_bars)
    trend_rows = list(trend_bars)
    trend = alligator_points(trend_rows, params)
    entry_points = alligator_points(entries, params)
    trend_by_time = {point.timestamp: point for point in trend}
    eastern = ZoneInfo("America/New_York")
    trend_close_times: dict[str, datetime] = {}
    for index, point in enumerate(trend):
        start = datetime.strptime(point.timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        close = start + timedelta(minutes=trend_interval_minutes)
        next_start = (
            datetime.strptime(trend[index + 1].timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if index + 1 < len(trend)
            else None
        )
        if infer_trend_close_from_session_boundaries:
            # IBKR RTH 4-hour data has a shorter opening segment (09:30-12:00
            # ET) followed by the afternoon segment. When another bar begins
            # on the same New York session date, that start is the completed
            # prior bar's actual boundary. The final segment ends at 16:00 ET.
            local_start = start.astimezone(eastern)
            if next_start is not None and next_start.astimezone(eastern).date() == local_start.date():
                close = next_start
            else:
                close = local_start.replace(hour=16, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        elif infer_shortened_trend_bars and next_start is not None:
            # Futures sessions can include exchange-maintenance and partial
            # segments. A next bar beginning sooner than the nominal duration
            # is the observed completion boundary; never extend a bar beyond
            # its nominal duration.
            close = min(close, next_start)
        trend_close_times[point.timestamp] = close
    signals: list[dict[str, object]] = []
    prior_long_ready = prior_short_ready = False

    for index, (bar, point) in enumerate(zip(entries, entry_points)):
        bar_start = datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        bar_close = bar_start + timedelta(minutes=entry_interval_minutes)
        completed_trend_times = [stamp for stamp, close_time in trend_close_times.items() if close_time <= bar_close]
        trend_point = trend_by_time[max(completed_trend_times)] if completed_trend_times else None
        long_ready = bool(
            trend_point
            and trend_point.bullish_open
            and point.bullish_open
            and point.lips is not None
            and min(point.ha_open, point.ha_close) > point.lips
        )
        short_ready = bool(
            trend_point
            and trend_point.bearish_open
            and point.bearish_open
            and point.lips is not None
            and max(point.ha_open, point.ha_close) < point.lips
        )
        # The completed bar creates the signal. The earliest permissible
        # historical fill is the next bar's open, never the current close.
        eastern_close = bar_close.astimezone(eastern)
        entry_window_open = eastern_close.weekday() < 5
        if minimum_decision_close_time is not None:
            opening_hour, opening_minute = minimum_decision_close_time
            entry_window_open = entry_window_open and (eastern_close.hour, eastern_close.minute) >= (
                opening_hour,
                opening_minute,
            )
        next_bar_is_immediate = False
        if index + 1 < len(entries):
            next_start = datetime.strptime(entries[index + 1].timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            next_bar_is_immediate = next_start == bar_close
        if entry_window_open and next_bar_is_immediate and point.jaw is not None:
            next_bar = entries[index + 1]
            if long_ready and not prior_long_ready:
                stop_distance = next_bar.open - point.jaw
                signals.append(
                    {
                        "decision_timestamp": bar_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "entry_timestamp": next_bar.timestamp,
                        "side": "long",
                        "entry_reference": next_bar.open,
                        "jaw": point.jaw,
                        "jaw_stop_distance_percent": stop_distance / next_bar.open,
                    }
                )
            if short_ready and not prior_short_ready:
                stop_distance = point.jaw - next_bar.open
                signals.append(
                    {
                        "decision_timestamp": bar_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "entry_timestamp": next_bar.timestamp,
                        "side": "short",
                        "entry_reference": next_bar.open,
                        "jaw": point.jaw,
                        "jaw_stop_distance_percent": stop_distance / next_bar.open,
                    }
                )
        prior_long_ready, prior_short_ready = long_ready, short_ready
    return signals
