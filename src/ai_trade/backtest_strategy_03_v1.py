"""Historical-only backtest for Strategy 03 v1 on 15-minute or 1-hour bars."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig, _entry_allowed, run_backtest, summarize, write_results
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_03_v1 import candidate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Strategy 03 v1 Alligator mouth-opening transitions.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--timeframe", choices=("15m", "1h"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bars = load_ohlcv_csv(args.bars)
    interval = 15 if args.timeframe == "15m" else 60
    config = BacktestConfig(
        allowed_direction="both", block_opening_hour_entries=True,
        block_final_hour_entries=True, block_friday_entries=True,
        entry_interval_minutes=interval, force_friday_close=True,
    )
    signals = candidate_signals(bars, interval_minutes=interval)
    eligible = [signal for signal in signals if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)]
    report: dict[str, object] = {
        "strategy_id": f"strategy_03_v1_{args.timeframe}_alligator_open",
        "mode": "historical_backtest_only",
        "data": {
            "symbol": args.symbol.upper(), "source": "locally cached IBKR historical bars",
            "timeframe": args.timeframe, "range": [bars[0].timestamp, bars[-1].timestamp],
        },
        "assumptions": {
            **asdict(config),
            "entry": "first completed bar transitioning into bullish/bearish open Alligator; fill at next bar open",
            "stop": "Jaw plus/minus max(minimum tick, 0.10 ATR)",
            "target": "1:1 realised entry-to-stop distance",
            "filters": "no VIX, macro, Heikin-Ashi, support/resistance, or higher-timeframe confirmation",
            "intrabar_collision": "stop before target",
        },
        "candidate_signal_count": len(signals), "eligible_signal_count": len(eligible), "results": {},
        "warning": "Historical research only; no paper or live order authorization.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in ("fixed", "rrms"):
        trades = run_backtest(bars, signals, mode, config)
        summary = summarize(trades, config.starting_equity)
        report["results"][mode] = summary
        write_results(trades, summary, mode, args.output)
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved Strategy 03 v1 {args.timeframe} backtest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
