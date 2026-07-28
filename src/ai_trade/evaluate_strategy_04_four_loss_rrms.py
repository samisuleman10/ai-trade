"""Evaluate saved Strategy 04 signals with the four-loss RRMS cycle."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ai_trade.backtest_strategy_01 import summarize, write_results
from ai_trade.backtest_strategy_04_v1 import _config
from ai_trade.rrms_four_loss_reset import FOUR_LOSS_TIERS, run_backtest_four_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.trade_statistics import ledger_statistics


def _load_signals(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--bars", required=True, type=Path)
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    bars = load_ohlcv_csv(args.bars)
    signals = _load_signals(args.signals)
    config = _config()
    trades = run_backtest_four_loss_reset(bars, signals, config)
    summary = summarize(trades, config.starting_equity)
    args.output.mkdir(parents=True, exist_ok=True)
    write_results(trades, summary, "rrms_four_loss", args.output)
    details = ledger_statistics(args.output / "rrms_four_loss_trades.csv")
    report = {
        "strategy_id": "strategy_04_v1_1_shallow_long_penetration",
        "symbol": args.symbol.upper(),
        "sizing_model": "four_loss_rrms",
        "tiers": list(FOUR_LOSS_TIERS),
        "reset": "after a profit or the fourth consecutive negative exit",
        "bars": str(args.bars),
        "signals": str(args.signals),
        "results": {**summary, "details": details},
    }
    (args.output / "four_loss_rrms_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
