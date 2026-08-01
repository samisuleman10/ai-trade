from datetime import datetime, timedelta, timezone

import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_causal_loop import ReactionContext, signals_from_zone_events
from ai_trade.strategy_04_indicator import ZoneEvent
from ai_trade.strategy_04_v1_1 import (
    Strategy04V11ExecutionParameters,
    signals_from_zone_events_v1_1,
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


# Two reactions on the same zone: the first (14:30, close 100.4) and, after a
# no-contact bar, a second shallower one (15:00, close 100.2).
_TWO_REACTION_BARS = [
    _bar("2026-01-06T14:15:00Z", 100.5, 100.7, 100.3, 100.5),
    _bar("2026-01-06T14:30:00Z", 100.2, 100.8, 99.75, 100.4),
    _bar("2026-01-06T14:45:00Z", 100.2, 100.5, 100.1, 100.3),
    _bar("2026-01-06T15:00:00Z", 100.0, 100.4, 99.9, 100.2),
    _bar("2026-01-06T15:15:00Z", 100.3, 100.5, 100.2, 100.4),
]

_PARAMS = Strategy04V11ExecutionParameters()


def test_without_hooks_matches_v1_1():
    # The bare loop is v1.1's behaviour; only the ATR timeline representation
    # differs, which must not change which signals exist or their values.
    bare = signals_from_zone_events(
        _TWO_REACTION_BARS, _hour_bars(), [_zone()], _PARAMS
    )
    v11 = signals_from_zone_events_v1_1(
        _TWO_REACTION_BARS, _hour_bars(), [_zone()], _PARAMS
    )
    assert bare == v11
    assert len(bare) == 1
    assert bare[0]["trigger_timestamp"] == "2026-01-06T14:30:00Z"


def test_rejected_reaction_leaves_zone_available():
    # Reject the first reaction only; the same zone must still fire later.
    def reject_first(zone, context):
        return context.bar.timestamp != "2026-01-06T14:30:00Z"

    signals = signals_from_zone_events(
        _TWO_REACTION_BARS,
        _hour_bars(),
        [_zone()],
        _PARAMS,
        reaction_filter=reject_first,
    )
    assert len(signals) == 1
    assert signals[0]["trigger_timestamp"] == "2026-01-06T15:00:00Z"


def test_rejecting_everything_yields_no_signals():
    signals = signals_from_zone_events(
        _TWO_REACTION_BARS,
        _hour_bars(),
        [_zone()],
        _PARAMS,
        reaction_filter=lambda zone, context: False,
    )
    assert signals == []


def test_extra_columns_are_appended_after_shared_ones():
    def columns(selected, context):
        side, stop = context.side_and_stop(selected)
        return {"extra_side": side, "extra_stop": stop}

    signal = signals_from_zone_events(
        _TWO_REACTION_BARS,
        _hour_bars(),
        [_zone()],
        _PARAMS,
        extra_columns=columns,
    )[0]
    assert list(signal)[-2:] == ["extra_side", "extra_stop"]
    assert signal["extra_side"] == signal["side"] == "long"
    # The helper's stop is the very one the emitted signal records.
    assert signal["extra_stop"] == signal["stop_reference"]


def test_side_and_stop_matches_both_zone_sides():
    context = ReactionContext(
        previous=_TWO_REACTION_BARS[0],
        bar=_TWO_REACTION_BARS[1],
        next_bar=_TWO_REACTION_BARS[2],
        decision_time=datetime(2026, 1, 6, 14, 45, tzinfo=timezone.utc),
        stop_buffer=0.1,
        latest_atr=2.0,
        latest_atr_timestamp=datetime(2026, 1, 6, 14, 0, tzinfo=timezone.utc),
        reference_open=100.0,
        reference_close=100.0,
    )

    class _Zone:
        def __init__(self, side):
            self.side = side
            self.lower = 99.0
            self.upper = 100.0

    assert context.side_and_stop(_Zone("demand")) == ("long", pytest.approx(98.9))
    assert context.side_and_stop(_Zone("supply")) == ("short", pytest.approx(100.1))
