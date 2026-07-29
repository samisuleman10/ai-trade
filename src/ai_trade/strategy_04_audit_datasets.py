"""Build Strategy 04's audit datasets for a published visualization bundle.

Phase 2 of docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md.
These are the datasets the dashboard's deep-dive reads instead of the
committed JSON fixtures it used to import, which meant a rerun updated the
ledger without updating the screen.

``audit_datasets_for`` returns an empty list for anything that is not an
auditable Strategy 04 run, so ``backfill_visualization_bundles`` can call it
for every discovered directory without knowing which strategy produced it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_trade.build_strategy_04_fixture import (
    FIFTEEN_MINUTE_BARS_AFTER,
    FIFTEEN_MINUTE_BARS_BEFORE,
    ONE_HOUR_BARS_AFTER,
    ONE_HOUR_BARS_BEFORE,
    SLIPPAGE_BPS,
    competing_zones,
    load_signals,
    load_trades,
    resolve_max_long_penetration,
    window,
)
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_audit import FifteenMinuteBar, audit_trade
from ai_trade.strategy_04_indicator import (
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
