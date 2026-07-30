"""Parameter sweep for Strategy 04 v1.2 Filter A's max_risk_zone_ratio.

Required by the v1.2 spec before any threshold may be trusted: the 2.5
default was chosen by inspecting the same data it was measured on. This
sweep reports fixed-risk outcomes across a threshold grid, per symbol, with
Filter A only (Filter B off, so any effect is attributable). The report is
evidence for a human decision -- nothing here selects a threshold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest, summarize
from ai_trade.backtest_strategy_04_v1_2_asset import symbol_run_inputs
from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    build_one_hour_indicator,
)
from ai_trade.strategy_04_v1_2 import (
    Strategy04V12ExecutionParameters,
    signals_from_zone_events_v1_2,
)

DEFAULT_THRESHOLDS = tuple(round(1.5 + 0.25 * step, 2) for step in range(11))  # 1.5 .. 4.0


def sweep_symbol(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    indicator_params: Strategy04IndicatorParameters,
    config: BacktestConfig,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> list[dict[str, object]]:
    """Build zones once, then evaluate Filter A alone at each threshold."""
    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    indicator = build_one_hour_indicator(hours, indicator_params)

    unfiltered = signals_from_zone_events_v1_2(
        fifteen, hours, indicator.events, Strategy04V12ExecutionParameters()
    )
    rows: list[dict[str, object]] = []
    for threshold in thresholds:
        params = Strategy04V12ExecutionParameters(
            enable_filter_a=True, max_risk_zone_ratio=threshold
        )
        signals = signals_from_zone_events_v1_2(fifteen, hours, indicator.events, params)
        trades = run_backtest(fifteen, signals, "fixed", config)
        summary = summarize(trades, config.starting_equity)
        rows.append(
            {
                "threshold": threshold,
                "candidate_signal_count": len(signals),
                "rejected_vs_unfiltered": len(unfiltered) - len(signals),
                "trade_count": summary["trade_count"],
                "win_rate": summary["win_rate"],
                "average_r": summary["average_r"],
                "net_pnl": summary["net_pnl"],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep Filter A's max_risk_zone_ratio per symbol.")
    parser.add_argument("--symbols", nargs="+",
                        choices=("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD"),
                        default=("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD"))
    parser.add_argument("--output", type=Path,
                        default=Path("strategies/strategy_04/v1_2/results/sweep"))
    args = parser.parse_args()

    report: dict[str, object] = {"thresholds": list(DEFAULT_THRESHOLDS), "symbols": {}}
    for symbol in args.symbols:
        fifteen_path, hours_path, config, indicator_params, market = symbol_run_inputs(symbol)
        rows = sweep_symbol(
            load_ohlcv_csv(fifteen_path), load_ohlcv_csv(hours_path),
            indicator_params, config,
        )
        report["symbols"][symbol] = {"market": market, "rows": rows}
        print(f"{symbol}: {json.dumps(rows[-1])}")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "risk_ratio_sweep.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Strategy 04 v1.2 -- max_risk_zone_ratio sweep (Filter A only)",
        "",
        "Fixed 0.15% risk. Filter B off throughout so effects are attributable.",
        "**No threshold is selected by this report.** The spec requires a human",
        "decision informed by sensitivity: a real edge should persist across",
        "neighbouring thresholds, not appear at exactly one value. All caveats",
        "from the v1.2 spec's Research warning apply, including that the 2.5",
        "exploratory split was chosen in-sample. Signal counts need not be",
        "monotonic in the threshold: a rejected reaction leaves its zone",
        "unconsumed, which can create additional later signals.",
        "",
    ]
    for symbol, block in report["symbols"].items():
        lines += [
            f"## {symbol}",
            "",
            "| Threshold | Signals | Rejected | Trades | Win rate | Avg R | Net P&L |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in block["rows"]:
            lines.append(
                f"| {row['threshold']} | {row['candidate_signal_count']} "
                f"| {row['rejected_vs_unfiltered']} | {row['trade_count']} "
                f"| {row['win_rate']:.3f} | {row['average_r']:+.4f} "
                f"| {row['net_pnl']:+.2f} |"
            )
        lines.append("")
    (args.output / "SWEEP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved sweep to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
