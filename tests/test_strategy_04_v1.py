from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import ZoneEvent
from ai_trade.strategy_04_v1 import signals_from_zone_events


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hour_bars() -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    return [
        OHLCVBar(
            timestamp=_stamp(start + timedelta(hours=index)),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
        for index in range(48)
    ]


def _bar(
    timestamp: str,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> OHLCVBar:
    return OHLCVBar(timestamp, open_, high, low, close, 1_000.0)


def _qualified(
    *,
    side: str,
    timestamp: str,
    zone_id: int = 7,
    lower: float = 99.0,
    upper: float = 100.0,
    score: int = 2,
) -> ZoneEvent:
    return ZoneEvent(
        timestamp=timestamp,
        zone_id=zone_id,
        event="qualified",
        side=side,
        lower=lower,
        upper=upper,
        score=score,
        details="pivot|repeated_pivot",
    )


def test_zone_becomes_eligible_only_after_qualification_timestamp():
    bars = [
        _bar("2026-01-06T14:00:00Z", 100.6, 100.8, 100.3, 100.5),
        # This candle closes when the zone qualifies, so it cannot use it.
        _bar("2026-01-06T14:15:00Z", 100.4, 100.6, 99.5, 100.5),
        # The zone existed before this candle opened, so this reaction counts.
        _bar("2026-01-06T14:30:00Z", 100.4, 100.7, 99.4, 100.6),
        _bar("2026-01-06T14:45:00Z", 100.7, 100.9, 100.5, 100.8),
    ]
    events = [_qualified(side="demand", timestamp="2026-01-06T14:30:00Z")]

    signals = signals_from_zone_events(bars, _hour_bars(), events)

    assert len(signals) == 1
    assert signals[0]["trigger_timestamp"] == "2026-01-06T14:30:00Z"
    assert signals[0]["decision_timestamp"] == "2026-01-06T14:45:00Z"
    assert signals[0]["entry_timestamp"] == "2026-01-06T14:45:00Z"
    assert signals[0]["side"] == "long"


def test_stop_uses_five_percent_of_latest_completed_hourly_atr():
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.4, 100.8, 99.4, 100.6),
        _bar("2026-01-06T14:45:00Z", 100.7, 100.9, 100.5, 100.8),
    ]
    events = [_qualified(side="demand", timestamp="2026-01-06T14:00:00Z")]

    signal = signals_from_zone_events(bars, _hour_bars(), events)[0]

    assert signal["one_hour_atr"] == 2.0
    assert signal["stop_buffer"] == 0.1
    assert signal["stop_reference"] == 98.9


def test_supply_reaction_creates_short_signal():
    bars = [
        _bar("2026-01-06T14:15:00Z", 98.4, 98.7, 98.2, 98.5),
        _bar("2026-01-06T14:30:00Z", 98.6, 99.5, 98.3, 98.4),
        _bar("2026-01-06T14:45:00Z", 98.3, 98.5, 98.0, 98.2),
    ]
    events = [
        _qualified(
            side="supply",
            timestamp="2026-01-06T14:00:00Z",
            lower=99.0,
            upper=100.0,
        )
    ]

    signal = signals_from_zone_events(bars, _hour_bars(), events)[0]

    assert signal["side"] == "short"
    assert signal["stop_reference"] == 100.1


def test_one_zone_can_create_only_one_signal():
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.4, 100.8, 99.4, 100.6),
        _bar("2026-01-06T14:45:00Z", 100.6, 100.9, 100.2, 100.5),
        _bar("2026-01-06T15:00:00Z", 100.4, 100.8, 99.5, 100.6),
        _bar("2026-01-06T15:15:00Z", 100.7, 100.9, 100.4, 100.8),
    ]
    events = [_qualified(side="demand", timestamp="2026-01-06T14:00:00Z")]

    signals = signals_from_zone_events(bars, _hour_bars(), events)

    assert len(signals) == 1
    assert signals[0]["zone_id"] == 7


def test_broken_zone_cannot_trigger():
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.4, 100.8, 99.4, 100.6),
        _bar("2026-01-06T14:45:00Z", 100.7, 100.9, 100.5, 100.8),
    ]
    events = [
        _qualified(side="demand", timestamp="2026-01-06T14:00:00Z"),
        ZoneEvent(
            timestamp="2026-01-06T14:15:00Z",
            zone_id=7,
            event="broken",
            side="demand",
            lower=99.0,
            upper=100.0,
            score=2,
        ),
    ]

    assert signals_from_zone_events(bars, _hour_bars(), events) == []

