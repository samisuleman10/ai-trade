"""Create a read-only diagnostic report for Strategy 01 from local SPY CSV bars."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ai_trade.strategy_01 import Strategy01Parameters, alligator_points, candidate_signals, load_ohlcv_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Alligator/Heikin-Ashi candidate signals from local SPY history.")
    parser.add_argument("--fifteen-minute", type=Path, default=Path("data/market_data/ibkr/SPY/spy_15m.csv"))
    parser.add_argument("--one-hour", type=Path, default=Path("data/market_data/ibkr/SPY/spy_1h.csv"))
    parser.add_argument("--output", type=Path, default=Path("outputs/strategy_01_diagnostic"))
    parser.add_argument("--slope-lookback", type=int, default=3)
    parser.add_argument("--minimum-separation-percent", type=float, default=0.0002)
    parser.add_argument("--allow-non-widening", action="store_true")
    args = parser.parse_args()
    params = Strategy01Parameters(
        slope_lookback_bars=args.slope_lookback,
        minimum_line_separation_percent=args.minimum_separation_percent,
        require_widening_separation=not args.allow_non_widening,
    )
    entries = load_ohlcv_csv(args.fifteen_minute)
    trend = load_ohlcv_csv(args.one_hour)
    signals = candidate_signals(entries, trend, params)
    points = alligator_points(entries, params)
    states = {
        "bullish_open_bars": sum(point.bullish_open for point in points),
        "bearish_open_bars": sum(point.bearish_open for point in points),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "candidate_signals.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "decision_timestamp",
                "entry_timestamp",
                "side",
                "entry_reference",
                "jaw",
                "jaw_stop_distance_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(signals)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": "strategy_01_bill_williams_alligator_rrms",
        "mode": "diagnostic_only",
        "parameters": asdict(params),
        "input": {"fifteen_minute_bars": len(entries), "one_hour_bars": len(trend)},
        "states": states,
        "candidate_signal_count": len(signals),
        "warning": "Candidate signals are diagnostics only. No fills, fees, RRMS sizing, macro filter, or order submission is included.",
    }
    report_path = args.output / "diagnostic_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(signals)} candidate signals to {args.output / 'candidate_signals.csv'}")
    print(f"Saved diagnostic report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
