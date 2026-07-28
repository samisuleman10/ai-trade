"""Historical-only backtest for locked Strategy 02 v1.5."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig, _entry_allowed, run_backtest, summarize, write_results
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_02_v1_5 import candidate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest locked Strategy 02 v1.5 from cached SPY bars.")
    parser.add_argument("--fifteen-minute", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"))
    parser.add_argument("--one-hour", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"))
    parser.add_argument("--output", type=Path, default=Path("strategies/strategy_02/v1_5/results/backtest"))
    args = parser.parse_args()

    fifteen = load_ohlcv_csv(args.fifteen_minute)
    hourly = load_ohlcv_csv(args.one_hour)
    config = BacktestConfig(
        allowed_direction="both",
        block_opening_hour_entries=True,
        block_final_hour_entries=True,
        block_friday_entries=True,
        entry_interval_minutes=15,
        force_friday_close=True,
    )
    signals = candidate_signals(fifteen, hourly)
    eligible = [
        signal for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]
    report: dict[str, object] = {
        "strategy_id": "strategy_02_v1_5_multi_timeframe_alligator_zigzag",
        "mode": "historical_backtest_only",
        "data": {
            "symbol": "SPY",
            "source": "locally cached IBKR historical bars",
            "fifteen_minute_range": [fifteen[0].timestamp, fifteen[-1].timestamp],
            "one_hour_range": [hourly[0].timestamp, hourly[-1].timestamp],
            "fifteen_minute_bar_count": len(fifteen),
            "one_hour_bar_count": len(hourly),
        },
        "assumptions": {
            **asdict(config),
            "confirmation": "completed 1-hour Heikin-Ashi body crosses the 1-hour Jaw while the 1-hour Alligator remains open in the pre-reversal direction",
            "alignment": "latest completed 15-minute Alligator agrees with the intended direction",
            "structure": "completed 15-minute ZigZag-style Heikin-Ashi support/resistance, Depth 18 / Deviation 5 ticks / Backstep 3",
            "entry": "next 15-minute bar open after the completed 1-hour confirmation",
            "target": "one times realised entry-to-stop distance (1:1)",
            "stop": "structure dot plus max($0.01, 0.10 × completed 15-minute ATR(14)) buffer",
            "session": "US regular trading hours only; no opening hour, final hour, or Friday entries",
            "weekend": "force-close in the final Friday 15-minute bar containing 16:00 New York time",
            "costs": "1 basis point adverse slippage per side plus $0.005 per share per side",
            "intrabar_collision": "stop assumed before target when both occur inside one 15-minute bar",
            "macro_filter": "not integrated; long and short candidates are both included",
        },
        "candidate_signal_count": len(signals),
        "eligible_signal_count": len(eligible),
        "results": {},
        "warning": "Preliminary research only. This is not a live or paper-trading authorization and excludes market impact, tax, borrow constraints, and a live macro filter.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in ("fixed", "rrms"):
        trades = run_backtest(fifteen, signals, mode, config)
        summary = summarize(trades, config.starting_equity)
        report["results"][mode] = summary
        write_results(trades, summary, mode, args.output)
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved Strategy 02 v1.5 backtest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
