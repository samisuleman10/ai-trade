"""Compare fixed sizing with weekly-reset RRMS for Strategy 03 v1 4-hour."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest, summarize, write_results
from ai_trade.rrms_weekly_reset import run_backtest_weekly_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_03_v1_4h import candidate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Strategy 03 4h with weekly-reset RRMS.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bars = load_ohlcv_csv(args.bars)
    signals = candidate_signals(bars)
    config = BacktestConfig(
        allowed_direction="both", block_opening_hour_entries=True,
        block_final_hour_entries=True, block_friday_entries=True,
        entry_interval_minutes=240, force_friday_close=True,
    )
    fixed_trades = run_backtest(bars, signals, "fixed", config)
    weekly_trades = run_backtest_weekly_reset(bars, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    weekly_summary = summarize(weekly_trades, config.starting_equity)
    args.output.mkdir(parents=True, exist_ok=True)
    write_results(fixed_trades, fixed_summary, "fixed", args.output)
    write_results(weekly_trades, weekly_summary, "rrms", args.output)
    report = {
        "strategy_id": "strategy_03_v1_4h_weekly_reset_rrms",
        "mode": "historical_backtest_only",
        "data": {"symbol": args.symbol.upper(), "timeframe": "4h", "range": [bars[0].timestamp, bars[-1].timestamp]},
        "assumptions": {
            **asdict(config),
            "rrms_tiers": [0.0015, 0.0035, 0.0070, 0.0150],
            "weekly_reset": "every new ISO trading week and every Friday forced close resets tier to 0",
            "maximum_tier_stop": "blocks only the remainder of the current week",
        },
        "candidate_signal_count": len(signals),
        "results": {"fixed": fixed_summary, "rrms": weekly_summary},
        "warning": "Historical research only; weekly-reset RRMS is not authorized for execution.",
    }
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved weekly-reset RRMS test to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
