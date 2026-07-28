from datetime import datetime, timedelta, timezone

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    Zone,
    _add_or_merge_zone,
    _session_profile,
    _update_zone_state,
    build_one_hour_indicator,
    strategy_04_v0_2_parameters,
    strategy_04_v0_3_parameters,
)


def _timestamp(index: int) -> str:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return (start + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bars_with_confirmed_low() -> list[OHLCVBar]:
    rows = []
    for index in range(32):
        low = 95.0 if index == 15 else 99.0 + abs(index - 15) * 0.03
        rows.append(
            OHLCVBar(
                timestamp=_timestamp(index),
                open=100.2,
                high=101.0 + abs(index - 15) * 0.02,
                low=low,
                close=100.3,
                volume=1_000 + index,
            )
        )
    return rows


def test_pivot_zone_uses_confirmation_bar_close_as_availability():
    bars = _bars_with_confirmed_low()
    params = Strategy04IndicatorParameters(
        pivot_left_bars=5,
        pivot_right_bars=3,
        minimum_confluence_score=2,
    )

    result = build_one_hour_indicator(bars, params)
    pivot = next(
        zone
        for zone in result.zones
        if zone.origin_side == "demand"
        and zone.origin_timestamp == bars[15].timestamp
        and "pivot" in zone.sources
    )

    assert pivot.available_timestamp == _timestamp(19)
    if pivot.qualified_timestamp:
        assert pivot.qualified_timestamp >= pivot.available_timestamp


def test_phase_one_indicator_never_creates_trade_or_order_signals():
    result = build_one_hour_indicator(_bars_with_confirmed_low())

    assert result.summary["trading_signals_generated"] == 0
    assert result.summary["orders_generated"] == 0
    assert result.summary["non_repainting_check_passed"] is True


def test_session_profile_places_poc_in_highest_volume_region():
    rows = [
        OHLCVBar(_timestamp(0), 100, 101, 99, 100, 100),
        OHLCVBar(_timestamp(1), 104, 105, 103, 104, 1_000),
    ]

    poc, vah, val = _session_profile(rows, bins=12, value_area_fraction=0.70)

    assert 103 <= poc <= 105
    assert val <= poc <= vah


def _candidate_zone(
    zone_id: int,
    lower: float,
    upper: float,
    source: str,
    pivot_count: int = 0,
) -> Zone:
    return Zone(
        zone_id=zone_id,
        origin_side="demand",
        side="demand",
        lower=lower,
        upper=upper,
        origin_timestamp=_timestamp(0),
        available_timestamp=_timestamp(1),
        created_bar_index=1,
        sources={source},
        source_details=[source],
        pivot_count=pivot_count,
        last_pivot_bar_index=1 if source == "pivot" else None,
    )


def test_v0_2_freezes_qualified_geometry_and_score_snapshot():
    params = strategy_04_v0_2_parameters()
    zones: list[Zone] = []
    events = []

    _add_or_merge_zone(
        zones, _candidate_zone(1, 100.0, 100.2, "pivot", 1),
        1.0, _timestamp(2), 2, params, events,
    )
    _add_or_merge_zone(
        zones, _candidate_zone(2, 100.1, 100.35, "order_block"),
        1.0, _timestamp(3), 3, params, events,
    )
    zone = zones[0]
    assert zone.qualified_score == 2
    assert zone.qualified_lower == 100.0
    assert zone.qualified_upper == 100.35

    _add_or_merge_zone(
        zones, _candidate_zone(3, 99.9, 100.4, "pivot", 1),
        1.0, _timestamp(4), 4, params, events,
    )

    assert (zone.lower, zone.upper) == (100.0, 100.35)
    assert zone.qualification_score == 2
    assert zone.score == 3
    assert any(event.event == "evidence_upgrade" for event in events)


def test_rejection_event_is_not_duplicated_during_one_continuous_contact():
    params = strategy_04_v0_2_parameters()
    zone = _candidate_zone(1, 99.0, 100.0, "pivot", 1)
    zone.qualified_timestamp = _timestamp(1)
    zone.qualified_bar_index = 1
    zone.qualified_lower = zone.lower
    zone.qualified_upper = zone.upper
    zone.qualified_score = 2
    zone.qualified_sources = ("order_block", "pivot")
    zone.sources.add("order_block")
    zone.status = "active"
    events = []
    first = OHLCVBar(_timestamp(2), 99.5, 101.0, 99.2, 100.5, 1_000)
    second = OHLCVBar(_timestamp(3), 100.2, 101.1, 99.4, 100.6, 1_100)

    _update_zone_state(zone, first, 2, 1.0, _timestamp(3), params, events)
    _update_zone_state(zone, second, 3, 1.0, _timestamp(4), params, events)

    assert sum(event.event == "touch" for event in events) == 1
    assert sum(event.event == "rejection" for event in events) == 1

def test_v0_3_requires_separated_repeated_pivot_before_qualification():
    params = strategy_04_v0_3_parameters()
    zones: list[Zone] = []
    events = []

    first = _candidate_zone(1, 100.0, 100.2, "pivot", 1)
    block = _candidate_zone(2, 100.1, 100.3, "order_block")
    _add_or_merge_zone(zones, first, 1.0, _timestamp(2), 2, params, events)
    _add_or_merge_zone(zones, block, 1.0, _timestamp(3), 3, params, events)
    assert zones[0].score == 2
    assert zones[0].qualified_timestamp is None

    close_pivot = _candidate_zone(3, 100.05, 100.25, "pivot", 1)
    close_pivot.last_pivot_bar_index = 3
    _add_or_merge_zone(
        zones, close_pivot, 1.0, _timestamp(4), 4, params, events
    )
    assert zones[0].pivot_count == 1
    assert zones[0].qualified_timestamp is None

    separated_pivot = _candidate_zone(4, 100.05, 100.25, "pivot", 1)
    separated_pivot.last_pivot_bar_index = 8
    _add_or_merge_zone(
        zones, separated_pivot, 1.0, _timestamp(9), 9, params, events
    )
    assert zones[0].pivot_count == 2
    assert zones[0].qualified_timestamp == _timestamp(9)
    assert "repeated_pivot" in zones[0].qualified_sources


def test_v0_3_rejection_requires_later_directional_confirmation_and_cooldown():
    params = strategy_04_v0_3_parameters()
    zone = _candidate_zone(1, 99.0, 100.0, "pivot", 1)
    zone.sources.add("repeated_pivot")
    zone.pivot_count = 2
    zone.qualified_timestamp = _timestamp(1)
    zone.qualified_bar_index = 1
    zone.qualified_lower = zone.lower
    zone.qualified_upper = zone.upper
    zone.qualified_score = 2
    zone.qualified_sources = ("pivot", "repeated_pivot")
    zone.status = "active"
    events = []

    approach = OHLCVBar(_timestamp(2), 100.6, 101.0, 100.4, 100.8, 1_000)
    touch = OHLCVBar(_timestamp(3), 100.2, 100.6, 99.6, 100.3, 1_100)
    confirmation = OHLCVBar(_timestamp(4), 100.1, 100.6, 100.05, 100.4, 1_200)
    cooldown_touch = OHLCVBar(_timestamp(5), 100.2, 100.4, 99.7, 100.3, 1_100)

    _update_zone_state(zone, approach, 2, 1.0, _timestamp(3), params, events)
    _update_zone_state(zone, touch, 3, 1.0, _timestamp(4), params, events)
    assert sum(event.event == "touch" for event in events) == 1
    assert sum(event.event == "rejection" for event in events) == 0

    _update_zone_state(
        zone, confirmation, 4, 1.0, _timestamp(5), params, events
    )
    _update_zone_state(
        zone, cooldown_touch, 5, 1.0, _timestamp(6), params, events
    )
    assert sum(event.event == "rejection" for event in events) == 1
    assert sum(event.event == "touch" for event in events) == 1
    assert zone.rejection_cooldown_until == 9
