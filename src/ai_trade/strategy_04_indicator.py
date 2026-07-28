"""Causal one-hour Confluence Reaction Zones indicator.

This module implements Strategy 04 Phase 1 only. It discovers and maintains
one-hour zones; it does not create 15-minute entries or submit orders.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import atr


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
NEW_YORK = ZoneInfo("America/New_York")
TERMINAL_STATES = {"expired", "invalidated"}
LIVE_STATES = {"candidate", "active", "touched", "rejected", "verified"}


@dataclass(frozen=True)
class Strategy04IndicatorParameters:
    """Locked v0.1 research defaults.

    Values are deliberately conservative and expressed in ATR units where
    possible so the same logic can be tested on other liquid instruments.
    """

    atr_period: int = 14
    pivot_left_bars: int = 5
    pivot_right_bars: int = 3
    pivot_min_width_atr: float = 0.12
    pivot_max_width_atr: float = 0.55
    structure_lookback_bars: int = 10
    order_block_lookback_bars: int = 6
    displacement_atr: float = 1.20
    merge_distance_atr: float = 0.25
    max_merged_width_atr: float = 1.00
    volume_profile_bins: int = 24
    volume_value_area: float = 0.70
    volume_reference_distance_atr: float = 0.30
    volume_reference_max_age_bars: int = 40
    volume_scoring_kinds: tuple[str, ...] = ("POC", "VAH", "VAL")
    minimum_confluence_score: int = 2
    invalidation_buffer_atr: float = 0.05
    max_zone_age_bars: int = 240
    broken_retest_window_bars: int = 40
    max_live_zones: int = 20
    freeze_qualified_geometry: bool = False
    minimum_pivot_separation_bars: int = 0
    require_repeated_pivot_for_qualification: bool = False
    staged_rejection: bool = False
    rejection_confirmation_window_bars: int = 3
    rejection_body_atr: float = 0.15
    rejection_cooldown_bars: int = 5

    def __post_init__(self) -> None:
        if min(self.atr_period, self.pivot_left_bars, self.pivot_right_bars) < 1:
            raise ValueError("ATR and pivot lengths must be positive")
        if self.order_block_lookback_bars < 1 or self.structure_lookback_bars < 2:
            raise ValueError("Structure and order-block lookbacks are invalid")
        if not 0 < self.volume_value_area <= 1:
            raise ValueError("Volume value area must be between 0 and 1")
        if self.volume_profile_bins < 4:
            raise ValueError("Volume profile needs at least four bins")
        if self.minimum_confluence_score < 1:
            raise ValueError("Minimum confluence score must be positive")
        if min(
            self.minimum_pivot_separation_bars,
            self.rejection_confirmation_window_bars,
            self.rejection_cooldown_bars,
        ) < 0:
            raise ValueError("Separation, confirmation, and cooldown bars cannot be negative")
        if self.rejection_body_atr < 0:
            raise ValueError("Rejection body threshold cannot be negative")


def strategy_04_v0_2_parameters() -> Strategy04IndicatorParameters:
    """Return the causal v0.2 preset while preserving locked v0.1 defaults."""
    return replace(
        Strategy04IndicatorParameters(),
        volume_reference_distance_atr=0.0,
        volume_reference_max_age_bars=8,
        volume_scoring_kinds=("POC",),
        freeze_qualified_geometry=True,
    )


def strategy_04_v0_3_parameters() -> Strategy04IndicatorParameters:
    """Return the selective v0.3 preset without changing earlier versions."""
    return replace(
        strategy_04_v0_2_parameters(),
        max_merged_width_atr=0.50,
        minimum_pivot_separation_bars=6,
        require_repeated_pivot_for_qualification=True,
        staged_rejection=True,
        rejection_confirmation_window_bars=3,
        rejection_body_atr=0.15,
        rejection_cooldown_bars=5,
    )


@dataclass(frozen=True)
class VolumeReference:
    session_date: str
    kind: str
    price: float
    available_timestamp: str
    available_bar_index: int


@dataclass
class Zone:
    zone_id: int
    origin_side: str
    side: str
    lower: float
    upper: float
    origin_timestamp: str
    available_timestamp: str
    created_bar_index: int
    qualified_lower: Optional[float] = None
    qualified_upper: Optional[float] = None
    qualified_score: Optional[int] = None
    qualified_sources: tuple[str, ...] = ()
    sources: set[str] = field(default_factory=set)
    source_details: list[str] = field(default_factory=list)
    pivot_count: int = 0
    last_pivot_bar_index: Optional[int] = None
    approach_ready: bool = False
    pending_touch_bar_index: Optional[int] = None
    rejection_cooldown_until: int = -1
    qualified_timestamp: Optional[str] = None
    qualified_bar_index: Optional[int] = None
    status: str = "candidate"
    touches: int = 0
    retests: int = 0
    in_contact: bool = False
    last_touch_timestamp: Optional[str] = None
    break_timestamp: Optional[str] = None
    break_bar_index: Optional[int] = None
    invalidated_timestamp: Optional[str] = None

    @property
    def score(self) -> int:
        return len(self.sources)

    @property
    def qualification_score(self) -> int:
        return self.qualified_score if self.qualified_score is not None else self.score


@dataclass(frozen=True)
class ZoneEvent:
    timestamp: str
    zone_id: int
    event: str
    side: str
    lower: float
    upper: float
    score: int
    details: str = ""


@dataclass(frozen=True)
class Strategy04IndicatorResult:
    zones: list[Zone]
    events: list[ZoneEvent]
    volume_references: list[VolumeReference]
    summary: dict[str, object]


def _parse(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _format(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(UTC_FORMAT)


def _bar_close_timestamp(bar: OHLCVBar) -> str:
    return _format(_parse(bar.timestamp) + timedelta(hours=1))


def _zone_distance(lower: float, upper: float, other_lower: float, other_upper: float) -> float:
    if lower <= other_upper and other_lower <= upper:
        return 0.0
    return min(abs(lower - other_upper), abs(other_lower - upper))


def _level_distance(zone: Zone, price: float) -> float:
    if zone.lower <= price <= zone.upper:
        return 0.0
    return min(abs(price - zone.lower), abs(price - zone.upper))


def _session_profile(
    rows: list[OHLCVBar], bins: int, value_area_fraction: float
) -> tuple[float, float, float]:
    """Return a reproducible bar-volume approximation of POC, VAH and VAL."""
    session_low = min(row.low for row in rows)
    session_high = max(row.high for row in rows)
    if session_high <= session_low:
        return session_low, session_low, session_low
    step = (session_high - session_low) / bins
    profile = [0.0] * bins
    for row in rows:
        first = max(0, min(bins - 1, int((row.low - session_low) / step)))
        last = max(0, min(bins - 1, int((row.high - session_low) / step)))
        count = max(last - first + 1, 1)
        allocation = max(row.volume, 0.0) / count
        for index in range(first, last + 1):
            profile[index] += allocation

    poc_index = max(range(bins), key=profile.__getitem__)
    target = sum(profile) * value_area_fraction
    accumulated = profile[poc_index]
    low_index = high_index = poc_index
    while accumulated < target and (low_index > 0 or high_index < bins - 1):
        below = profile[low_index - 1] if low_index > 0 else -1.0
        above = profile[high_index + 1] if high_index < bins - 1 else -1.0
        if above >= below and high_index < bins - 1:
            high_index += 1
            accumulated += profile[high_index]
        elif low_index > 0:
            low_index -= 1
            accumulated += profile[low_index]
        else:
            break

    center = lambda index: session_low + (index + 0.5) * step
    return center(poc_index), center(high_index), center(low_index)


def session_volume_references(
    bars: Iterable[OHLCVBar], params: Strategy04IndicatorParameters
) -> list[VolumeReference]:
    """Build prior-session references with an explicit causal availability time."""
    rows = list(bars)
    sessions: dict[str, list[tuple[int, OHLCVBar]]] = defaultdict(list)
    for index, bar in enumerate(rows):
        session_date = _parse(bar.timestamp).astimezone(NEW_YORK).date().isoformat()
        sessions[session_date].append((index, bar))

    references: list[VolumeReference] = []
    for session_date, indexed_rows in sessions.items():
        session_rows = [row for _, row in indexed_rows]
        last_index, last_bar = indexed_rows[-1]
        available = _bar_close_timestamp(last_bar)
        poc, vah, val = _session_profile(
            session_rows, params.volume_profile_bins, params.volume_value_area
        )
        for kind, price in (("POC", poc), ("VAH", vah), ("VAL", val)):
            references.append(
                VolumeReference(
                    session_date=session_date,
                    kind=kind,
                    price=price,
                    available_timestamp=available,
                    available_bar_index=last_index,
                )
            )
    return sorted(references, key=lambda item: (item.available_bar_index, item.kind))


def _pivot_candidate(
    rows: list[OHLCVBar],
    atr_values: list[Optional[float]],
    confirmation_index: int,
    side: str,
    params: Strategy04IndicatorParameters,
    zone_id: int,
) -> Optional[Zone]:
    candidate = confirmation_index - params.pivot_right_bars
    start = candidate - params.pivot_left_bars
    end = candidate + params.pivot_right_bars + 1
    if start < 0 or candidate < 0 or end > len(rows):
        return None
    volatility = atr_values[confirmation_index]
    if volatility is None or volatility <= 0:
        return None
    window = rows[start:end]
    pivot = rows[candidate]
    if side == "supply":
        if pivot.high != max(row.high for row in window):
            return None
        # Resolve equal highs to the most recent candidate in the confirmation window.
        if candidate != start + max(i for i, row in enumerate(window) if row.high == pivot.high):
            return None
        wick_lower = max(pivot.open, pivot.close)
        width = min(
            max(pivot.high - wick_lower, params.pivot_min_width_atr * volatility),
            params.pivot_max_width_atr * volatility,
        )
        lower, upper = pivot.high - width, pivot.high
    else:
        if pivot.low != min(row.low for row in window):
            return None
        if candidate != start + max(i for i, row in enumerate(window) if row.low == pivot.low):
            return None
        wick_upper = min(pivot.open, pivot.close)
        width = min(
            max(wick_upper - pivot.low, params.pivot_min_width_atr * volatility),
            params.pivot_max_width_atr * volatility,
        )
        lower, upper = pivot.low, pivot.low + width
    return Zone(
        zone_id=zone_id,
        origin_side=side,
        side=side,
        lower=lower,
        upper=upper,
        origin_timestamp=pivot.timestamp,
        available_timestamp=_bar_close_timestamp(rows[confirmation_index]),
        created_bar_index=confirmation_index,
        sources={"pivot"},
        source_details=[f"pivot:{pivot.timestamp}"],
        pivot_count=1,
        last_pivot_bar_index=confirmation_index,
    )


def _order_block_candidate(
    rows: list[OHLCVBar],
    atr_values: list[Optional[float]],
    index: int,
    params: Strategy04IndicatorParameters,
    zone_id: int,
) -> Optional[Zone]:
    volatility = atr_values[index]
    if volatility is None or volatility <= 0 or index < params.structure_lookback_bars:
        return None
    current = rows[index]
    previous = rows[index - params.structure_lookback_bars:index]
    bullish_break = (
        current.close > max(row.high for row in previous)
        and current.close > current.open
        and current.close - current.open >= params.displacement_atr * volatility
    )
    bearish_break = (
        current.close < min(row.low for row in previous)
        and current.close < current.open
        and current.open - current.close >= params.displacement_atr * volatility
    )
    if not bullish_break and not bearish_break:
        return None
    search_start = max(0, index - params.order_block_lookback_bars)
    if bullish_break:
        candidates = [i for i in range(search_start, index) if rows[i].close < rows[i].open]
        if not candidates:
            return None
        origin_index = candidates[-1]
        origin = rows[origin_index]
        lower, upper = origin.low, max(origin.open, origin.close)
        side = "demand"
    else:
        candidates = [i for i in range(search_start, index) if rows[i].close > rows[i].open]
        if not candidates:
            return None
        origin_index = candidates[-1]
        origin = rows[origin_index]
        lower, upper = min(origin.open, origin.close), origin.high
        side = "supply"
    max_width = params.max_merged_width_atr * volatility
    if upper - lower > max_width:
        if side == "demand":
            upper = lower + max_width
        else:
            lower = upper - max_width
    return Zone(
        zone_id=zone_id,
        origin_side=side,
        side=side,
        lower=lower,
        upper=upper,
        origin_timestamp=origin.timestamp,
        available_timestamp=_bar_close_timestamp(current),
        created_bar_index=index,
        sources={"order_block"},
        source_details=[
            f"order_block:{origin.timestamp}",
            f"structure_break:{current.timestamp}",
        ],
    )


def _event(zone: Zone, timestamp: str, name: str, details: str = "") -> ZoneEvent:
    return ZoneEvent(
        timestamp=timestamp,
        zone_id=zone.zone_id,
        event=name,
        side=zone.side,
        lower=zone.lower,
        upper=zone.upper,
        score=zone.score,
        details=details,
    )


def _qualify(
    zone: Zone,
    timestamp: str,
    bar_index: int,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> None:
    base_structure_ready = (
        not params.require_repeated_pivot_for_qualification
        or ("pivot" in zone.sources and "repeated_pivot" in zone.sources)
    )
    if (
        zone.qualified_timestamp is None
        and zone.score >= params.minimum_confluence_score
        and base_structure_ready
    ):
        zone.qualified_timestamp = timestamp
        zone.qualified_bar_index = bar_index
        zone.qualified_lower = zone.lower
        zone.qualified_upper = zone.upper
        zone.qualified_score = zone.score
        zone.qualified_sources = tuple(sorted(zone.sources))
        zone.status = "active"
        events.append(_event(zone, timestamp, "qualified", "|".join(zone.qualified_sources)))


def _add_or_merge_zone(
    zones: list[Zone],
    candidate: Zone,
    volatility: float,
    timestamp: str,
    bar_index: int,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> Zone:
    matches: list[tuple[float, Zone]] = []
    for zone in zones:
        if zone.status not in LIVE_STATES or zone.side != candidate.side:
            continue
        distance = _zone_distance(zone.lower, zone.upper, candidate.lower, candidate.upper)
        merged_width = max(zone.upper, candidate.upper) - min(zone.lower, candidate.lower)
        if (
            distance <= params.merge_distance_atr * volatility
            and merged_width <= params.max_merged_width_atr * volatility
        ):
            matches.append((distance, zone))
    if not matches:
        zones.append(candidate)
        events.append(_event(candidate, timestamp, "created", "|".join(sorted(candidate.sources))))
        _qualify(candidate, timestamp, bar_index, params, events)
        return candidate

    _, target = min(matches, key=lambda item: (item[0], abs((item[1].lower + item[1].upper) / 2 - (candidate.lower + candidate.upper) / 2)))
    was_qualified = target.qualified_timestamp is not None
    previous_score = target.score
    geometry_frozen = params.freeze_qualified_geometry and was_qualified
    if not geometry_frozen:
        target.lower = min(target.lower, candidate.lower)
        target.upper = max(target.upper, candidate.upper)
    target.sources.update(candidate.sources)
    target.source_details.extend(
        detail for detail in candidate.source_details if detail not in target.source_details
    )
    candidate_is_pivot = "pivot" in candidate.sources and candidate.pivot_count > 0
    if candidate_is_pivot:
        candidate_pivot_index = (
            candidate.last_pivot_bar_index
            if candidate.last_pivot_bar_index is not None
            else bar_index
        )
        if target.last_pivot_bar_index is None:
            target.pivot_count = max(target.pivot_count, 1)
            target.last_pivot_bar_index = candidate_pivot_index
        elif (
            candidate_pivot_index - target.last_pivot_bar_index
            >= params.minimum_pivot_separation_bars
        ):
            target.pivot_count += 1
            target.last_pivot_bar_index = candidate_pivot_index
    if target.pivot_count >= 2:
        target.sources.add("repeated_pivot")
    events.append(
        _event(
            target,
            timestamp,
            "merged",
            f"{'|'.join(sorted(candidate.sources))};geometry={'frozen' if geometry_frozen else 'updated'}",
        )
    )
    if was_qualified and target.score > previous_score:
        events.append(
            _event(
                target,
                timestamp,
                "evidence_upgrade",
                f"score:{previous_score}->{target.score};qualified_score:{target.qualification_score}",
            )
        )
    _qualify(target, timestamp, bar_index, params, events)
    return target


def _attach_volume_references(
    zones: list[Zone],
    references: list[VolumeReference],
    volatility: float,
    timestamp: str,
    bar_index: int,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> None:
    for zone in zones:
        if zone.status not in LIVE_STATES:
            continue
        matches = [
            reference
            for reference in references
            if reference.kind in params.volume_scoring_kinds
            and 0 <= bar_index - reference.available_bar_index <= params.volume_reference_max_age_bars
            and _level_distance(zone, reference.price)
            <= params.volume_reference_distance_atr * volatility
        ]
        if not matches or "volume_profile" in zone.sources:
            continue
        closest = min(matches, key=lambda reference: _level_distance(zone, reference.price))
        was_qualified = zone.qualified_timestamp is not None
        previous_score = zone.score
        zone.sources.add("volume_profile")
        zone.source_details.append(
            f"volume:{closest.kind}:{closest.session_date}:{closest.price:.6f}"
        )
        events.append(
            _event(
                zone,
                timestamp,
                "volume_confluence",
                f"{closest.kind}:{closest.session_date}:{closest.price:.6f}",
            )
        )
        if was_qualified and zone.score > previous_score:
            events.append(
                _event(
                    zone,
                    timestamp,
                    "evidence_upgrade",
                    f"volume_profile;score:{previous_score}->{zone.score};qualified_score:{zone.qualification_score}",
                )
            )
        _qualify(zone, timestamp, bar_index, params, events)


def _update_staged_rejection(
    zone: Zone,
    bar: OHLCVBar,
    bar_index: int,
    volatility: float,
    timestamp: str,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> None:
    contact = bar.low <= zone.upper and bar.high >= zone.lower
    pending = zone.pending_touch_bar_index
    if pending is not None and bar_index > pending:
        inside_window = (
            bar_index - pending <= params.rejection_confirmation_window_bars
        )
        directional_body = abs(bar.close - bar.open) >= params.rejection_body_atr * volatility
        confirmed = inside_window and directional_body and (
            (
                zone.side == "demand"
                and bar.close > zone.upper
                and bar.close > bar.open
            )
            or (
                zone.side == "supply"
                and bar.close < zone.lower
                and bar.close < bar.open
            )
        )
        if confirmed:
            zone.status = "rejected"
            zone.pending_touch_bar_index = None
            zone.rejection_cooldown_until = bar_index + params.rejection_cooldown_bars
            events.append(_event(zone, timestamp, "rejection"))
        elif bar_index - pending > params.rejection_confirmation_window_bars:
            zone.pending_touch_bar_index = None

    new_contact = contact and not zone.in_contact
    cooldown_complete = bar_index > zone.rejection_cooldown_until
    if new_contact and zone.approach_ready and cooldown_complete:
        zone.touches += 1
        zone.last_touch_timestamp = timestamp
        zone.status = "touched"
        zone.pending_touch_bar_index = bar_index
        zone.approach_ready = False
        events.append(_event(zone, timestamp, "touch"))

    if not contact and cooldown_complete:
        outside_on_valid_side = (
            (zone.side == "demand" and bar.low > zone.upper)
            or (zone.side == "supply" and bar.high < zone.lower)
        )
        if outside_on_valid_side:
            zone.approach_ready = True
    zone.in_contact = contact


def _update_zone_state(
    zone: Zone,
    bar: OHLCVBar,
    bar_index: int,
    volatility: float,
    timestamp: str,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> None:
    if zone.status in TERMINAL_STATES:
        return
    if zone.status == "broken":
        assert zone.break_bar_index is not None
        if bar_index - zone.break_bar_index > params.broken_retest_window_bars:
            zone.status = "expired"
            zone.invalidated_timestamp = timestamp
            events.append(_event(zone, timestamp, "broken_zone_expired"))
            return
        contact = bar.low <= zone.upper and bar.high >= zone.lower
        if not contact:
            return
        if zone.side == "demand" and bar.close < zone.lower:
            zone.side = "supply"
        elif zone.side == "supply" and bar.close > zone.upper:
            zone.side = "demand"
        else:
            return
        zone.status = "verified"
        zone.retests += 1
        zone.sources.add("role_flip")
        zone.in_contact = True
        zone.approach_ready = False
        zone.pending_touch_bar_index = None
        zone.rejection_cooldown_until = bar_index + params.rejection_cooldown_bars
        zone.last_touch_timestamp = timestamp
        events.append(_event(zone, timestamp, "role_flip_retest"))
        return

    if bar_index - zone.created_bar_index > params.max_zone_age_bars:
        zone.status = "expired"
        zone.invalidated_timestamp = timestamp
        events.append(_event(zone, timestamp, "age_expired"))
        return

    buffer = params.invalidation_buffer_atr * volatility
    if zone.side == "demand" and bar.close < zone.lower - buffer:
        zone.status = "broken"
        zone.break_timestamp = timestamp
        zone.break_bar_index = bar_index
        zone.in_contact = False
        zone.approach_ready = False
        zone.pending_touch_bar_index = None
        events.append(_event(zone, timestamp, "broken"))
        return
    if zone.side == "supply" and bar.close > zone.upper + buffer:
        zone.status = "broken"
        zone.break_timestamp = timestamp
        zone.break_bar_index = bar_index
        zone.in_contact = False
        zone.approach_ready = False
        zone.pending_touch_bar_index = None
        events.append(_event(zone, timestamp, "broken"))
        return

    if params.staged_rejection:
        _update_staged_rejection(
            zone, bar, bar_index, volatility, timestamp, params, events
        )
        return

    contact = bar.low <= zone.upper and bar.high >= zone.lower
    new_contact = contact and not zone.in_contact
    if new_contact:
        zone.touches += 1
        zone.last_touch_timestamp = timestamp
        zone.status = "touched"
        events.append(_event(zone, timestamp, "touch"))
    if contact:
        rejected = (
            (zone.side == "demand" and bar.close > zone.upper)
            or (zone.side == "supply" and bar.close < zone.lower)
        )
        if rejected and (new_contact or zone.status != "rejected"):
            zone.status = "rejected"
            events.append(_event(zone, timestamp, "rejection"))
    zone.in_contact = contact


def _prune_live_zones(
    zones: list[Zone],
    timestamp: str,
    params: Strategy04IndicatorParameters,
    events: list[ZoneEvent],
) -> None:
    live = [zone for zone in zones if zone.status in LIVE_STATES]
    if len(live) <= params.max_live_zones:
        return
    excess = len(live) - params.max_live_zones
    ordered = sorted(
        live,
        key=lambda zone: (
            zone.qualified_timestamp is not None,
            zone.score,
            zone.created_bar_index,
        ),
    )
    for zone in ordered[:excess]:
        zone.status = "expired"
        zone.invalidated_timestamp = timestamp
        events.append(_event(zone, timestamp, "capacity_expired"))


def build_one_hour_indicator(
    bars: Iterable[OHLCVBar],
    params: Strategy04IndicatorParameters = Strategy04IndicatorParameters(),
) -> Strategy04IndicatorResult:
    """Build the one-hour indicator chronologically without future leakage."""
    rows = list(bars)
    if not rows:
        raise ValueError("At least one OHLCV bar is required")
    atr_values = atr(rows, params.atr_period)
    references = session_volume_references(rows, params)
    references_by_index: dict[int, list[VolumeReference]] = defaultdict(list)
    for reference in references:
        references_by_index[reference.available_bar_index].append(reference)

    zones: list[Zone] = []
    events: list[ZoneEvent] = []
    active_references: list[VolumeReference] = []
    next_zone_id = 1

    for index, bar in enumerate(rows):
        timestamp = _bar_close_timestamp(bar)
        volatility = atr_values[index]
        active_references.extend(references_by_index.get(index, []))
        active_references = [
            reference
            for reference in active_references
            if index - reference.available_bar_index <= params.volume_reference_max_age_bars
        ]
        if volatility is None or volatility <= 0:
            continue

        # Existing zones react only to bars completed after they became available.
        for zone in zones:
            if zone.created_bar_index < index:
                _update_zone_state(
                    zone, bar, index, volatility, timestamp, params, events
                )

        for side in ("demand", "supply"):
            candidate = _pivot_candidate(
                rows, atr_values, index, side, params, next_zone_id
            )
            if candidate is not None:
                _add_or_merge_zone(
                    zones,
                    candidate,
                    volatility,
                    timestamp,
                    index,
                    params,
                    events,
                )
                next_zone_id += 1

        order_block = _order_block_candidate(
            rows, atr_values, index, params, next_zone_id
        )
        if order_block is not None:
            _add_or_merge_zone(
                zones,
                order_block,
                volatility,
                timestamp,
                index,
                params,
                events,
            )
            next_zone_id += 1

        _attach_volume_references(
            zones,
            active_references,
            volatility,
            timestamp,
            index,
            params,
            events,
        )
        _prune_live_zones(zones, timestamp, params, events)

    qualified = [zone for zone in zones if zone.qualified_timestamp is not None]
    status_counts = Counter(zone.status for zone in qualified)
    score_counts = Counter(str(zone.score) for zone in qualified)
    qualification_score_counts = Counter(str(zone.qualification_score) for zone in qualified)
    event_counts = Counter(event.event for event in events if any(
        zone.zone_id == event.zone_id and zone.qualified_timestamp is not None
        for zone in qualified
    ))
    violations = [
        zone.zone_id
        for zone in qualified
        if _parse(zone.qualified_timestamp or zone.available_timestamp)
        < _parse(zone.available_timestamp)
    ]
    geometry_freeze_violations = [
        zone.zone_id
        for zone in qualified
        if params.freeze_qualified_geometry
        and (
            zone.qualified_lower is None
            or zone.qualified_upper is None
            or abs(zone.lower - zone.qualified_lower) > 1e-9
            or abs(zone.upper - zone.qualified_upper) > 1e-9
        )
    ]
    summary: dict[str, object] = {
        "bar_count": len(rows),
        "first_timestamp": rows[0].timestamp,
        "last_timestamp": rows[-1].timestamp,
        "raw_zone_count": len(zones),
        "qualified_zone_count": len(qualified),
        "qualified_demand_count": sum(zone.origin_side == "demand" for zone in qualified),
        "qualified_supply_count": sum(zone.origin_side == "supply" for zone in qualified),
        "status_counts": dict(sorted(status_counts.items())),
        "score_counts": dict(sorted(score_counts.items())),
        "current_score_counts": dict(sorted(score_counts.items())),

        "qualification_score_counts": dict(sorted(qualification_score_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "volume_reference_count": len(references),
        "non_repainting_violation_zone_ids": violations,
        "qualified_geometry_freeze_violation_zone_ids": geometry_freeze_violations,
        "non_repainting_check_passed": not violations and not geometry_freeze_violations,
        "trading_signals_generated": 0,
        "orders_generated": 0,
    }
    return Strategy04IndicatorResult(zones, events, references, summary)


def zone_record(zone: Zone) -> dict[str, object]:
    return {
        "zone_id": zone.zone_id,
        "origin_side": zone.origin_side,
        "current_side": zone.side,
        "lower": zone.lower,
        "upper": zone.upper,
        "origin_timestamp": zone.origin_timestamp,
        "available_timestamp": zone.available_timestamp,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "qualified_lower": zone.qualified_lower if zone.qualified_lower is not None else "",
        "qualified_upper": zone.qualified_upper if zone.qualified_upper is not None else "",
        "qualified_score": zone.qualified_score if zone.qualified_score is not None else "",
        "qualified_sources": "|".join(zone.qualified_sources),
        "status": zone.status,
        "score": zone.score,
        "current_score": zone.score,
        "sources": "|".join(sorted(zone.sources)),
        "source_details": "|".join(zone.source_details),
        "pivot_count": zone.pivot_count,
        "last_pivot_bar_index": zone.last_pivot_bar_index if zone.last_pivot_bar_index is not None else "",
        "approach_ready": zone.approach_ready,
        "pending_touch_bar_index": zone.pending_touch_bar_index if zone.pending_touch_bar_index is not None else "",
        "rejection_cooldown_until": zone.rejection_cooldown_until,
        "touches": zone.touches,
        "retests": zone.retests,
        "last_touch_timestamp": zone.last_touch_timestamp or "",
        "break_timestamp": zone.break_timestamp or "",
        "invalidated_timestamp": zone.invalidated_timestamp or "",
    }


def event_record(event: ZoneEvent) -> dict[str, object]:
    return {
        "timestamp": event.timestamp,
        "zone_id": event.zone_id,
        "event": event.event,
        "side": event.side,
        "lower": event.lower,
        "upper": event.upper,
        "score": event.score,
        "details": event.details,
    }

