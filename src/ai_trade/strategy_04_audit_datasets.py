"""Build Strategy 04's audit datasets for a published visualization bundle.

Phase 2 of docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md.
These are the datasets the dashboard's deep-dive reads. Before them it
imported committed JSON fixtures, so rerunning a backtest updated the trade
ledger while the screen kept showing the previous run's audit.

audit_datasets_for returns an empty list for anything that is not an
auditable Strategy 04 run, so backfill_visualization_bundles can call it
for every discovered directory without knowing which strategy produced it.

Zone geometry for the selected zone comes from the recorded signal row, not
from the rebuilt zone object, because a zone's side and status keep changing
after the trigger. The rebuilt timeline supplies only the qualification
timestamp and the competing zones, which the CSVs never recorded.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_audit import (
    FifteenMinuteBar,
    SignalRecord,
    TradeRecord,
    audit_trade,
)
from ai_trade.strategy_04_indicator import (
    Zone,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.visualization_contract import (
    ContractError,
    Dataset,
    build_audit_windows,
    build_trade_audit,
    build_zones,
)

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
ONE_HOUR_BARS_BEFORE = 40
ONE_HOUR_BARS_AFTER = 10
FIFTEEN_MINUTE_BARS_BEFORE = 20
FIFTEEN_MINUTE_BARS_AFTER = 20
SLIPPAGE_BPS = 1.0

# The long-side demand-zone penetration cap each strategy version states.
# ``None`` means the version has no such rule; v1 predates it entirely and
# its candidate_signals.csv has no penetration column at all. v1.2 keeps
# v1.1's 0.25 cap and adds trigger-distance and 1h-direction filters on top.
MAX_LONG_PENETRATION_BY_VERSION: dict[str, Optional[float]] = {
    "v1": None,
    "v1_1": 0.25,
    "v1_2": 0.25,
}


def _parse(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _optional_float(value: Optional[str]) -> Optional[float]:
    """Blank cells and absent columns stay None so neither reads as zero.

    v1's candidate_signals.csv predates the penetration rule and has no
    long_zone_penetration_fraction column at all, so ``value`` may be
    ``None`` here (from ``dict.get`` on a missing key), not just ``""``.
    """

    return float(value) if value else None


def load_signals(path: Path) -> list[SignalRecord]:
    """Read candidate_signals.csv into typed records."""

    records: list[SignalRecord] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(
                SignalRecord(
                    decision_timestamp=row["decision_timestamp"],
                    entry_timestamp=row["entry_timestamp"],
                    side=row["side"],
                    zone_id=int(row["zone_id"]),
                    zone_side=row["zone_side"],
                    zone_lower=float(row["zone_lower"]),
                    zone_upper=float(row["zone_upper"]),
                    trigger_timestamp=row["trigger_timestamp"],
                    trigger_low=float(row["trigger_low"]),
                    one_hour_atr=float(row["one_hour_atr"]),
                    one_hour_atr_timestamp=row["one_hour_atr_timestamp"],
                    stop_buffer=float(row["stop_buffer"]),
                    long_zone_penetration_fraction=_optional_float(
                        row.get("long_zone_penetration_fraction")
                    ),
                    reward_to_risk=float(row["reward_to_risk"]),
                )
            )
    return records


def load_trades(path: Path) -> list[TradeRecord]:
    """Read a trade ledger CSV into typed records."""

    records: list[TradeRecord] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(
                TradeRecord(
                    decision_timestamp=row["decision_timestamp"],
                    entry_timestamp=row["entry_timestamp"],
                    exit_timestamp=row["exit_timestamp"],
                    side=row["side"],
                    quantity=int(row["quantity"]),
                    entry_price=float(row["entry_price"]),
                    stop_price=float(row["stop_price"]),
                    target_price=float(row["target_price"]),
                    exit_price=float(row["exit_price"]),
                    exit_reason=row["exit_reason"],
                    net_pnl=float(row["net_pnl"]),
                    result_r=float(row["result_r"]),
                )
            )
    return records


def window(
    bars: Sequence[OHLCVBar],
    start: str,
    end: str,
    before: int,
    after: int,
) -> list[OHLCVBar]:
    """Return bars spanning start..end, padded and clipped to the series."""

    start_at = _parse(start)
    end_at = _parse(end)
    inside = [index for index, bar in enumerate(bars) if start_at <= _parse(bar.timestamp) <= end_at]
    if not inside:
        return []
    first = max(0, inside[0] - before)
    last = min(len(bars), inside[-1] + after + 1)
    return list(bars[first:last])


def _zone_by_id(zones: Sequence[Zone], zone_id: int) -> Optional[Zone]:
    for zone in zones:
        if zone.zone_id == zone_id:
            return zone
    return None


def competing_zones(zones: Sequence[Zone], selected: Zone, signal: SignalRecord) -> list[Zone]:
    """Zones qualified before the trigger that overlap the selected zone's range."""

    trigger_at = _parse(signal.trigger_timestamp)
    results: list[Zone] = []
    for zone in zones:
        if zone.zone_id == selected.zone_id or not zone.qualified_timestamp:
            continue
        if _parse(zone.qualified_timestamp) >= trigger_at:
            continue
        if zone.break_timestamp and _parse(zone.break_timestamp) < trigger_at:
            continue
        if zone.invalidated_timestamp and _parse(zone.invalidated_timestamp) < trigger_at:
            continue
        lower = zone.qualified_lower if zone.qualified_lower is not None else zone.lower
        upper = zone.qualified_upper if zone.qualified_upper is not None else zone.upper
        if lower <= signal.zone_upper and upper >= signal.zone_lower:
            results.append(zone)
    return results


def max_long_penetration_for(strategy_version: str) -> Optional[float]:
    """The long-side demand-zone penetration cap this version's rules state.

    ``None`` means the version has no penetration rule at all, which is
    true only of v1. Raises ``ValueError`` for a version this table does
    not know: guessing "no rule" for an unrecognised version would turn
    an unknown into a silent pass, which is exactly the failure mode this
    table exists to prevent. Add the version here when you add it.
    """

    if strategy_version not in MAX_LONG_PENETRATION_BY_VERSION:
        raise ValueError(
            "no penetration rule recorded for strategy version %r; add it to "
            "MAX_LONG_PENETRATION_BY_VERSION or pass --max-long-penetration "
            "explicitly" % (strategy_version,)
        )
    return MAX_LONG_PENETRATION_BY_VERSION[strategy_version]


def resolve_max_long_penetration(explicit: Optional[str], strategy_version: str) -> Optional[float]:
    """Resolve the cap: an explicit flag wins, otherwise the version decides.

    ``explicit`` is the raw ``--max-long-penetration`` argument, or
    ``None`` when the flag was not supplied at all. That distinction is
    the entire point. The flag used to default to ``None``, and ``None``
    means "this version has no penetration rule" -- so forgetting the
    flag while auditing v1.1 raised no error and no warning, it just
    turned a real rule into an unconditional pass for every long trade.

    Absence now means "ask the version"; passing ``none`` is the only way
    to assert that no rule applies. An unrecognised version with no
    explicit flag fails loudly (see ``max_long_penetration_for``), while
    an explicit value is accepted for any version -- a stated value is
    evidence, and only the silent default was dangerous.
    """

    if explicit is None:
        return max_long_penetration_for(strategy_version)
    if explicit.strip().lower() == "none":
        return None
    return float(explicit)


REPORT_FILENAME = "backtest_report.json"
SIGNALS_FILENAME = "candidate_signals.csv"
TRADES_FILENAME = "fixed_trades.csv"

# Rebuilding the one-hour zone timeline walks every bar in the cache -- about
# nine thousand for SPY, and several seconds each time. The six Strategy 04
# result directories share only three bar files between them (one per symbol,
# reused by v1 and v1.1), so without this memo a backfill pays for the same
# walk twice per symbol. Keyed on the resolved path and the file's mtime and
# size, so editing the bars invalidates the entry rather than serving a stale
# timeline.
_INDICATOR_CACHE: Dict[Tuple[str, int, int], Any] = {}


def _indicator_for(one_hour_path: Path) -> Any:
    stat = one_hour_path.stat()
    key = (str(one_hour_path.resolve()), stat.st_mtime_ns, stat.st_size)
    cached = _INDICATOR_CACHE.get(key)
    if cached is None:
        cached = build_one_hour_indicator(
            load_ohlcv_csv(one_hour_path), strategy_04_v0_3_parameters()
        )
        _INDICATOR_CACHE[key] = cached
    return cached


def report_bar_paths(report: Any) -> Optional[Tuple[str, str]]:
    """Return the (one_hour, fifteen_minute) bar paths the run recorded.

    Paths are stored as written on the producing machine, so Windows
    separators are normalized. Returns ``None`` when either is absent:
    deriving them from the symbol instead would guess, and a v4 versus v5
    bar cache would silently audit against different data than the backtest
    consumed.
    """

    if not isinstance(report, dict):
        return None
    data = report.get("data")
    if not isinstance(data, dict):
        return None
    one_hour = data.get("one_hour_file")
    fifteen = data.get("fifteen_minute_file")
    if not one_hour or not fifteen:
        return None
    return str(one_hour).replace("\\", "/"), str(fifteen).replace("\\", "/")


def _bar_json(bar: Any) -> Dict[str, Any]:
    return {
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _zone_json(zone: Any, lower: float, upper: float, side: str) -> Dict[str, Any]:
    return {
        "zone_id": zone.zone_id,
        "side": side,
        "lower": lower,
        "upper": upper,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "score": zone.qualification_score,
    }


def _version_from_path(result_dir: Path) -> str:
    for part in reversed(result_dir.parts):
        if len(part) > 1 and part[0] == "v" and all(ch.isdigit() or ch == "_" for ch in part[1:]):
            return part
    return "unknown"


def _default_indicator_parameters() -> Dict[str, Any]:
    """The v0.3 defaults, JSON-normalized.

    Round-tripping through JSON turns dataclass tuple fields (like
    ``volume_scoring_kinds``) into lists, matching how a report on disk
    stores them. Comparing the dataclass's ``asdict()`` directly against a
    loaded report would report a spurious mismatch on type alone.
    """

    return json.loads(json.dumps(asdict(strategy_04_v0_3_parameters())))


def _uses_default_indicator_parameters(report: Dict[str, Any]) -> bool:
    """True unless the report recorded a non-default indicator parameter.

    The zone timeline rebuild always uses ``strategy_04_v0_3_parameters()``
    (see ``_indicator_for``), so a run recorded with different parameters
    -- the FX runs' ``profile_weighting="time"``,
    ``session_day_boundary="fx_17et"`` -- would be audited against a
    differently-shaped timeline. Zone ids are stable within a run but not
    across parameter sets, so some ids would resolve to geometrically
    different zones (including demand/supply flips) rather than raising.

    Reports older than the ``profile_weighting`` / ``session_day_boundary``
    fields simply omit them; that absence describes the same behaviour the
    current defaults encode, not a mismatch, so a missing key reads as a
    match. Only a recorded value that disagrees with the default counts.
    """

    recorded = report.get("indicator_parameters")
    if not isinstance(recorded, dict):
        return True
    default = _default_indicator_parameters()
    return all(recorded.get(key, value) == value for key, value in default.items())


def _auditable_report(result_dir: Path) -> Optional[Dict[str, Any]]:
    report_path = result_dir / REPORT_FILENAME
    if not report_path.is_file():
        return None
    if not (result_dir / SIGNALS_FILENAME).is_file() or not (result_dir / TRADES_FILENAME).is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    if not str(report.get("strategy_id", "")).startswith("strategy_04"):
        return None
    if not _uses_default_indicator_parameters(report):
        # Honest skip: the signal audit's rebuilt zone timeline always uses
        # the v0.3 defaults, which do not describe this run. Returning None
        # here (rather than raising) means audit_datasets_for returns []
        # for this directory -- the bundle still publishes with its ledger
        # audit, just without has_signal_audit / audit windows, exactly as
        # a non-strategy-04 run is treated.
        return None
    return report


def audit_datasets_for(result_dir: Any, repo_root: Any) -> List[Dataset]:
    """Zones, rule checks and bar windows for one Strategy 04 result directory.

    Trade ids are constructed exactly as ``build_trade_ledger`` constructs
    them -- ``<result-dir-name>:fixed:<six-digit ordinal>`` over the same
    ledger in the same order -- because the dashboard joins these datasets
    to the ledger on that id.
    """

    result_dir = Path(result_dir)
    repo_root = Path(repo_root)

    report = _auditable_report(result_dir)
    if report is None:
        return []
    bar_paths = report_bar_paths(report)
    if bar_paths is None:
        return []

    one_hour_path = repo_root / bar_paths[0]
    fifteen_minute_path = repo_root / bar_paths[1]
    if not one_hour_path.is_file() or not fifteen_minute_path.is_file():
        return []

    signals = {s.decision_timestamp: s for s in load_signals(result_dir / SIGNALS_FILENAME)}
    trades = load_trades(result_dir / TRADES_FILENAME)

    hour_bars = load_ohlcv_csv(one_hour_path)
    minute_bars = load_ohlcv_csv(fifteen_minute_path)
    # The audit takes only timestamp and open, so it stays free of the IBKR
    # client that market_data.OHLCVBar drags in.
    audit_bars = [FifteenMinuteBar(bar.timestamp, bar.open) for bar in minute_bars]
    indicator = _indicator_for(one_hour_path)
    zones_by_id = {zone.zone_id: zone for zone in indicator.zones}

    strategy_version = report.get("strategy_version") or _version_from_path(result_dir)
    cap = resolve_max_long_penetration(None, strategy_version)

    run_id = result_dir.name
    zone_entries: List[Dict[str, Any]] = []
    audit_entries: List[Dict[str, Any]] = []
    window_entries: List[Dict[str, Any]] = []

    for ordinal, trade in enumerate(trades, start=1):
        trade_id = "%s:fixed:%06d" % (run_id, ordinal)
        signal = signals.get(trade.decision_timestamp)
        if signal is None:
            raise ContractError(
                "trade %s has no candidate signal at %s" % (trade_id, trade.decision_timestamp)
            )
        selected = zones_by_id.get(signal.zone_id)
        if selected is None:
            raise ContractError(
                "zone %d referenced by %s is missing from the rebuilt timeline"
                % (signal.zone_id, trade.decision_timestamp)
            )

        checks = audit_trade(
            signal,
            trade,
            selected.qualified_timestamp or "",
            audit_bars,
            cap,
            SLIPPAGE_BPS,
        )
        audit_entries.append(
            {
                "trade_id": trade_id,
                "trigger_timestamp": signal.trigger_timestamp,
                "checks": [
                    {
                        "check_id": check.check_id,
                        "passed": check.passed,
                        "expected": check.expected,
                        "actual": check.actual,
                    }
                    for check in checks
                ],
            }
        )
        zone_entries.append(
            {
                "trade_id": trade_id,
                "selected": _zone_json(
                    selected, signal.zone_lower, signal.zone_upper, signal.zone_side
                ),
                "competing": [
                    _zone_json(
                        zone,
                        zone.qualified_lower if zone.qualified_lower is not None else zone.lower,
                        zone.qualified_upper if zone.qualified_upper is not None else zone.upper,
                        zone.origin_side,
                    )
                    for zone in competing_zones(indicator.zones, selected, signal)
                ],
            }
        )
        window_entries.append(
            {
                "trade_id": trade_id,
                "one_hour": [
                    _bar_json(bar)
                    for bar in window(
                        hour_bars,
                        selected.qualified_timestamp or trade.entry_timestamp,
                        trade.exit_timestamp,
                        ONE_HOUR_BARS_BEFORE,
                        ONE_HOUR_BARS_AFTER,
                    )
                ],
                "fifteen_minute": [
                    _bar_json(bar)
                    for bar in window(
                        minute_bars,
                        signal.trigger_timestamp,
                        trade.exit_timestamp,
                        FIFTEEN_MINUTE_BARS_BEFORE,
                        FIFTEEN_MINUTE_BARS_AFTER,
                    )
                ],
            }
        )

    return [
        build_zones(zone_entries),
        build_trade_audit(audit_entries),
        build_audit_windows(window_entries),
    ]
