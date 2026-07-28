"""Historical-only Strategy 02 v2 backtest with completed 15-minute VIX filter."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig, _entry_allowed, run_backtest, summarize, write_results
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_02_v2 import candidate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Strategy 02 v2 with VIX < 20.")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--fifteen-minute", type=Path, required=True)
    parser.add_argument("--one-hour", type=Path, required=True)
    parser.add_argument("--vix-fifteen-minute", type=Path, default=Path("data/market_data/ibkr/VIX/v2/vix_15m.csv"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fifteen, hourly, vix = load_ohlcv_csv(args.fifteen_minute), load_ohlcv_csv(args.one_hour), load_ohlcv_csv(args.vix_fifteen_minute)
    config = BacktestConfig(allowed_direction="both", block_opening_hour_entries=True, block_final_hour_entries=True,
                            block_friday_entries=True, entry_interval_minutes=15, force_friday_close=True)
    signals = candidate_signals(fifteen, hourly, vix)
    eligible = [s for s in signals if _entry_allowed(str(s["entry_timestamp"]), str(s["side"]), config)]
    report: dict[str, object] = {
        "strategy_id": "strategy_02_v2_vix_under_20",
        "mode": "historical_backtest_only",
        "data": {"symbol": args.symbol.upper(), "source": "locally cached IBKR historical bars",
                 "fifteen_minute_range": [fifteen[0].timestamp, fifteen[-1].timestamp],
                 "one_hour_range": [hourly[0].timestamp, hourly[-1].timestamp],
                 "vix_fifteen_minute_range": [vix[0].timestamp, vix[-1].timestamp]},
        "assumptions": {**asdict(config), "base_strategy": "Strategy 02 v1.5", "vix_filter": "latest completed 15-minute VIX close strictly below 20.00",
                        "macro_filter": "not integrated", "target": "1:1 realised entry-to-stop distance", "intrabar_collision": "stop before target"},
        "candidate_signal_count": len(signals), "eligible_signal_count": len(eligible), "results": {},
        "warning": "Preliminary historical research only; no live or paper order authorization.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in ("fixed", "rrms"):
        trades = run_backtest(fifteen, signals, mode, config)
        summary = summarize(trades, config.starting_equity)
        report["results"][mode] = summary
        write_results(trades, summary, mode, args.output)
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved Strategy 02 v2 backtest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
