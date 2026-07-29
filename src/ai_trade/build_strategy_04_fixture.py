"""Build the Strategy 04 dashboard fixture from real backtest artifacts.

Phase 1 of docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md.
Output shape matches the visualization contract so Phase 2 can serve the same
JSON from the API with no dashboard component changes.

Zone geometry for the selected zone comes from the recorded signal row, not
from the rebuilt zone object, because a zone's side and status keep changing
after the trigger. The rebuilt timeline supplies only the qualification
timestamp and the competing zones, which the CSVs never recorded.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_audit import (
    CheckResult,
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

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SCHEMA_VERSION = "1.0.0"
ONE_HOUR_BARS_BEFORE = 40
ONE_HOUR_BARS_AFTER = 10
FIFTEEN_MINUTE_BARS_BEFORE = 20
FIFTEEN_MINUTE_BARS_AFTER = 20
SLIPPAGE_BPS = 1.0


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
                    entry_price=float(row["entry_price"]),
                    stop_price=float(row["stop_price"]),
                    target_price=float(row["target_price"]),
                    exit_price=float(row["exit_price"]),
                    exit_reason=row["exit_reason"],
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


def _bar_json(bar: OHLCVBar) -> dict:
    return {
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _selected_zone_json(signal: SignalRecord, zone: Zone) -> dict:
    """Geometry and side from the recorded signal; qualification from the timeline."""

    return {
        "zone_id": signal.zone_id,
        "side": signal.zone_side,
        "lower": signal.zone_lower,
        "upper": signal.zone_upper,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "score": zone.qualification_score,
    }


def _competing_zone_json(zone: Zone) -> dict:
    """Competing zones use the geometry frozen at qualification."""

    lower = zone.qualified_lower if zone.qualified_lower is not None else zone.lower
    upper = zone.qualified_upper if zone.qualified_upper is not None else zone.upper
    return {
        "zone_id": zone.zone_id,
        "side": zone.origin_side,
        "lower": lower,
        "upper": upper,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "score": zone.qualification_score,
    }


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


def _check_json(check: CheckResult) -> dict:
    return {
        "check_id": check.check_id,
        "passed": check.passed,
        "expected": check.expected,
        "actual": check.actual,
    }


def build_fixture(
    results_dir: Path,
    one_hour_path: Path,
    fifteen_minute_path: Path,
    symbol: str,
    strategy_version: str,
    max_long_penetration: Optional[float],
) -> dict:
    """Assemble the complete fixture document.

    ``max_long_penetration`` is a property of the strategy version being
    audited, not a fixed constant: v1 has no shallow-penetration rule at all
    (pass ``None``), while v1.1 caps it at 0.25. Passing the wrong value for
    a version would make the audit report a false violation or silently miss
    a real one.
    """

    signals = {
        signal.decision_timestamp: signal
        for signal in load_signals(results_dir / "candidate_signals.csv")
    }
    trades = load_trades(results_dir / "fixed_trades.csv")
    summary = json.loads((results_dir / "fixed_summary.json").read_text(encoding="utf-8"))

    hour_bars = load_ohlcv_csv(one_hour_path)
    minute_bars = load_ohlcv_csv(fifteen_minute_path)
    # The audit needs each entry bar's OPEN as well as its timestamp: the
    # recorded entry_price is only verifiable against the bar it came from.
    audit_bars = [FifteenMinuteBar(bar.timestamp, bar.open) for bar in minute_bars]

    indicator = build_one_hour_indicator(hour_bars, strategy_04_v0_3_parameters())

    trade_documents = []
    for ordinal, trade in enumerate(trades, start=1):
        signal = signals[trade.decision_timestamp]
        selected = _zone_by_id(indicator.zones, signal.zone_id)
        if selected is None:
            raise ValueError(
                "Zone %d referenced by %s is missing from the rebuilt timeline"
                % (signal.zone_id, trade.decision_timestamp)
            )

        checks = audit_trade(
            signal,
            trade,
            selected.qualified_timestamp or "",
            audit_bars,
            max_long_penetration,
            SLIPPAGE_BPS,
        )
        hour_window_start = selected.qualified_timestamp or trade.entry_timestamp
        trade_documents.append(
            {
                "trade_id": "%s_%s:fixed:%06d" % (strategy_version, symbol.lower(), ordinal),
                "ordinal": ordinal,
                "decision_timestamp": trade.decision_timestamp,
                "entry_timestamp": trade.entry_timestamp,
                "exit_timestamp": trade.exit_timestamp,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "stop_price": trade.stop_price,
                "target_price": trade.target_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "result_r": trade.result_r,
                "trigger_timestamp": signal.trigger_timestamp,
                "audit": {
                    "passed": all(check.passed for check in checks),
                    "checks": [_check_json(check) for check in checks],
                },
                "zones": {
                    "selected": _selected_zone_json(signal, selected),
                    "competing": [
                        _competing_zone_json(zone)
                        for zone in competing_zones(indicator.zones, selected, signal)
                    ],
                },
                "bars": {
                    "one_hour": [
                        _bar_json(bar)
                        for bar in window(
                            hour_bars,
                            hour_window_start,
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
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": "strategy_04_%s_%s_1h_15m" % (strategy_version, symbol.lower()),
        "execution_authority": "none",
        "run": {"strategy_id": "strategy_04", "strategy_version": strategy_version},
        "instrument": {"symbol": symbol},
        "summary": {
            "trade_count": len(trade_documents),
            "audit_passed": sum(1 for item in trade_documents if item["audit"]["passed"]),
            "audit_failed": sum(1 for item in trade_documents if not item["audit"]["passed"]),
            "net_pnl": summary["net_pnl"],
            "ending_equity": summary["ending_equity"],
        },
        "trades": trade_documents,
    }


def _max_long_penetration_type(value: str) -> Optional[float]:
    """Parse ``--max-long-penetration``: 'none' (any case) disables the rule."""

    if value.strip().lower() == "none":
        return None
    return float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Strategy 04 dashboard fixture.")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("strategies/strategy_04/v1_1/results/spy_1h_15m"),
    )
    parser.add_argument(
        "--one-hour",
        type=Path,
        default=Path("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
    )
    parser.add_argument(
        "--fifteen-minute",
        type=Path,
        default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"),
    )
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--strategy-version", default="v1_1")
    parser.add_argument(
        "--max-long-penetration",
        type=_max_long_penetration_type,
        default=None,
        help=(
            "Maximum allowed long-side demand-zone penetration fraction for "
            "this strategy version. Omit, or pass 'none', for a version with "
            "no penetration rule (e.g. v1). Pass a number (e.g. 0.25) for a "
            "version that has the rule (e.g. v1.1)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dashboard/src/fixtures/strategy_04_v1_1_spy.json"),
    )
    args = parser.parse_args()

    fixture = build_fixture(
        args.results,
        args.one_hour,
        args.fifteen_minute,
        args.symbol,
        args.strategy_version,
        args.max_long_penetration,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Wrote %s with %d trades" % (args.output, len(fixture["trades"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
