from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import ZoneEvent
from ai_trade.strategy_04_v1_1 import signals_from_zone_events_v1_1


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hour_bars() -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    return [
        OHLCVBar(_stamp(start + timedelta(hours=i)), 100, 101, 99, 100, 1_000)
        for i in range(48)
    ]


def _bar(timestamp: str, open_: float, high: float, low: float, close: float) -> OHLCVBar:
    return OHLCVBar(timestamp, open_, high, low, close, 1_000)


def _zone(side: str = "demand") -> ZoneEvent:
    return ZoneEvent(
        timestamp="2026-01-06T14:00:00Z",
        zone_id=7,
        event="qualified",
        side=side,
        lower=99.0,
        upper=100.0,
        score=2,
        details="pivot|repeated_pivot",
    )


def test_deep_long_penetration_is_filtered():
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.4, 100.8, 99.4, 100.6),
        _bar("2026-01-06T14:45:00Z", 100.7, 100.9, 100.5, 100.8),
    ]
    assert signals_from_zone_events_v1_1(bars, _hour_bars(), [_zone()]) == []


def test_25_percent_long_penetration_is_allowed():
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.2, 100.8, 99.75, 100.4),
        _bar("2026-01-06T14:45:00Z", 100.5, 100.9, 100.4, 100.8),
    ]
    signal = signals_from_zone_events_v1_1(bars, _hour_bars(), [_zone()])[0]
    assert signal["side"] == "long"
    assert signal["long_zone_penetration_fraction"] == 0.25


def test_short_rules_are_unchanged():
    bars = [
        _bar("2026-01-06T14:15:00Z", 98.4, 98.7, 98.2, 98.5),
        _bar("2026-01-06T14:30:00Z", 98.6, 99.8, 98.3, 98.4),
        _bar("2026-01-06T14:45:00Z", 98.3, 98.5, 98.0, 98.2),
    ]
    signal = signals_from_zone_events_v1_1(bars, _hour_bars(), [_zone("supply")])[0]
    assert signal["side"] == "short"
    assert signal["long_zone_penetration_fraction"] is None
