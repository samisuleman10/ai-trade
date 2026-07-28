"""Test Strategy 03 v1 4-hour with capped five-loss RRMS."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest, summarize, write_results
from ai_trade.rrms_five_loss_reset import FIVE_LOSS_TIERS, run_backtest_five_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_03_v1_4h import candidate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Strategy 03 4h with capped five-loss RRMS.")
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
    rrms_trades = run_backtest_five_loss_reset(bars, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    rrms_summary = summarize(rrms_trades, config.starting_equity)
    args.output.mkdir(parents=True, exist_ok=True)
    write_results(fixed_trades, fixed_summary, "fixed", args.output)
    write_results(rrms_trades, rrms_summary, "rrms", args.output)
    report = {
        "strategy_id": "strategy_03_v1_4h_five_loss_capped_rrms",
        "mode": "historical_backtest_only",
        "data": {"symbol": args.symbol.upper(), "timeframe": "4h", "range": [bars[0].timestamp, bars[-1].timestamp]},
        "assumptions": {
            **asdict(config), "rrms_tiers": list(FIVE_LOSS_TIERS),
            "loss_definition": "every negative net exit, including Friday forced close",
            "reset": "any profit or the fifth consecutive loss",
            "weekly_reset": False,
        },
        "candidate_signal_count": len(signals),
        "results": {"fixed": fixed_summary, "rrms": rrms_summary},
        "warning": "Historical research only; capped five-loss RRMS is not authorized for execution.",
    }
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved capped five-loss RRMS test to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
