"""Run and persist Strategy 04 Phase 1 one-hour indicator analysis."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    build_one_hour_indicator,
    event_record,
    strategy_04_v0_2_parameters,
    strategy_04_v0_3_parameters,
    zone_record,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Strategy 04 one-hour confluence zones without trades."
    )
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--version", choices=("0.1", "0.2", "0.3"), default="0.1")
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.version == "0.3":
        params = strategy_04_v0_3_parameters()
    elif args.version == "0.2":
        params = strategy_04_v0_2_parameters()
    else:
        params = Strategy04IndicatorParameters()
    bars = load_ohlcv_csv(args.bars)
    result = build_one_hour_indicator(bars, params)
    args.output.mkdir(parents=True, exist_ok=True)

    all_zones = [zone_record(zone) for zone in result.zones]
    qualified = [
        zone_record(zone)
        for zone in result.zones
        if zone.qualified_timestamp is not None
    ]
    _write_csv(args.output / "all_zones.csv", all_zones)
    _write_csv(args.output / "qualified_zones.csv", qualified)
    _write_csv(
        args.output / "zone_events.csv",
        [event_record(event) for event in result.events],
    )
    _write_csv(
        args.output / "volume_references.csv",
        [asdict(reference) for reference in result.volume_references],
    )

    report = {
        "strategy_id": "strategy_04_phase_1_confluence_reaction_zones",
        "version": args.version,
        "mode": "one_hour_indicator_analysis_only",
        "symbol": args.symbol.upper(),
        "timeframe": "1h",
        "data_file": str(args.bars),
        "parameters": asdict(params),
        "summary": result.summary,
        "execution": {
            "fifteen_minute_logic_enabled": False,
            "trade_signals_enabled": False,
            "order_submission_enabled": False,
        },
        "warning": (
            "Research prototype. Volume-at-price is a documented hourly-bar "
            "approximation, not tick-level exchange volume."
        ),
    }
    (args.output / "indicator_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result.summary, indent=2))
    print(f"Saved Strategy 04 one-hour indicator analysis to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
