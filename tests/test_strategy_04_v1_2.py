from datetime import datetime, timedelta, timezone

import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import ZoneEvent
from ai_trade.strategy_04_v1_1 import signals_from_zone_events_v1_1
from ai_trade.strategy_04_v1_2 import (
    Strategy04V12ExecutionParameters,
    signals_from_zone_events_v1_2,
)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hour_bars(open_: float = 100.0, close: float = 100.0) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    return [
        OHLCVBar(_stamp(start + timedelta(hours=i)), open_, 101, 99, close, 1_000)
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


# Shallow long reaction: close 100.4, stop 99 - 0.05*ATR(2) = 98.9, width 1.0
# => risk_zone_ratio = (100.4 - 98.9) / 1.0 = 1.5
_LONG_BARS = [
    _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
    _bar("2026-01-06T14:30:00Z", 100.2, 100.8, 99.75, 100.4),
    _bar("2026-01-06T14:45:00Z", 100.5, 100.9, 100.4, 100.8),
]

_SHORT_BARS = [
    _bar("2026-01-06T14:15:00Z", 98.4, 98.7, 98.2, 98.5),
    _bar("2026-01-06T14:30:00Z", 98.6, 99.8, 98.3, 98.4),
    _bar("2026-01-06T14:45:00Z", 98.3, 98.5, 98.0, 98.2),
]


def test_parameter_defaults_and_validation():
    params = Strategy04V12ExecutionParameters()
    assert params.enable_filter_a is False
    assert params.enable_filter_b is False
    assert params.max_risk_zone_ratio == 2.5
    assert params.max_long_zone_penetration_fraction == 0.25  # v1.1 inherited
    with pytest.raises(ValueError):
        Strategy04V12ExecutionParameters(max_risk_zone_ratio=0)
    with pytest.raises(ValueError):
        Strategy04V12ExecutionParameters(max_risk_zone_ratio=-1.0)


def test_base_reproduces_v1_1_long_and_short():
    for bars, zone in ((_LONG_BARS, _zone()), (_SHORT_BARS, _zone("supply"))):
        v11 = signals_from_zone_events_v1_1(bars, _hour_bars(), [zone])
        v12 = signals_from_zone_events_v1_2(bars, _hour_bars(), [zone])
        assert len(v11) == len(v12) == 1
        stripped = {
            key: value
            for key, value in v12[0].items()
            if key not in (
                "risk_zone_ratio",
                "one_hour_reference_open",
                "one_hour_reference_close",
            )
        }
        assert stripped == v11[0]


def test_new_columns_are_appended_last_and_correct():
    signal = signals_from_zone_events_v1_2(_LONG_BARS, _hour_bars(), [_zone()])[0]
    assert list(signal)[-3:] == [
        "risk_zone_ratio",
        "one_hour_reference_open",
        "one_hour_reference_close",
    ]
    assert signal["risk_zone_ratio"] == pytest.approx(1.5)
    assert signal["one_hour_reference_open"] == 100.0
    assert signal["one_hour_reference_close"] == 100.0


def test_filter_a_rejects_above_threshold_and_allows_boundary():
    reject = Strategy04V12ExecutionParameters(enable_filter_a=True, max_risk_zone_ratio=1.4)
    assert signals_from_zone_events_v1_2(_LONG_BARS, _hour_bars(), [_zone()], reject) == []
    boundary = Strategy04V12ExecutionParameters(enable_filter_a=True, max_risk_zone_ratio=1.5)
    assert len(signals_from_zone_events_v1_2(_LONG_BARS, _hour_bars(), [_zone()], boundary)) == 1


def test_filter_a_rejection_does_not_consume_the_zone():
    # First reaction (ratio 1.5) is rejected at threshold 1.4; a later,
    # shallower reaction (ratio 1.3) on the SAME zone must still qualify.
    bars = [
        _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
        _bar("2026-01-06T14:30:00Z", 100.2, 100.8, 99.75, 100.4),  # ratio 1.5
        _bar("2026-01-06T14:45:00Z", 100.2, 100.5, 100.1, 100.3),  # no zone contact
        _bar("2026-01-06T15:00:00Z", 100.0, 100.4, 99.9, 100.2),   # ratio 1.3
        _bar("2026-01-06T15:15:00Z", 100.3, 100.5, 100.2, 100.4),
    ]
    params = Strategy04V12ExecutionParameters(enable_filter_a=True, max_risk_zone_ratio=1.4)
    signals = signals_from_zone_events_v1_2(bars, _hour_bars(), [_zone()], params)
    assert len(signals) == 1
    assert signals[0]["trigger_timestamp"] == "2026-01-06T15:00:00Z"
    assert signals[0]["risk_zone_ratio"] == pytest.approx(1.3)
    # Without the filter the first reaction consumes the zone instead.
    base = signals_from_zone_events_v1_2(bars, _hour_bars(), [_zone()])
    assert len(base) == 1
    assert base[0]["trigger_timestamp"] == "2026-01-06T14:30:00Z"


def test_filter_b_rejects_opposing_hour_and_permits_doji():
    bearish_hours = _hour_bars(open_=100.6, close=100.0)
    on = Strategy04V12ExecutionParameters(enable_filter_b=True)
    # Long against a bearish reference hour: rejected.
    assert signals_from_zone_events_v1_2(_LONG_BARS, bearish_hours, [_zone()], on) == []
    # Short with a bearish reference hour: agrees, allowed.
    assert len(signals_from_zone_events_v1_2(_SHORT_BARS, bearish_hours, [_zone("supply")], on)) == 1
    # Doji reference (open == close) permits both directions.
    assert len(signals_from_zone_events_v1_2(_LONG_BARS, _hour_bars(), [_zone()], on)) == 1
    # Filter B off: the bearish hour does not matter.
    assert len(signals_from_zone_events_v1_2(_LONG_BARS, bearish_hours, [_zone()])) == 1
