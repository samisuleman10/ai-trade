"""Cross-variant ablation table for Strategy 04 v1.2.

Reads the twenty committed backtest reports (5 symbols x 4 variants) and
writes one comparison table so filter effects can be attributed per symbol,
per the spec's required ablation. Interpretation stays with the human: the
spec's promotion criteria require out-of-sample confirmation and sensitivity
evidence that this table alone cannot provide.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SYMBOLS = ("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD")
VARIANTS = ("base", "a", "b", "ab")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the v1.2 ablation grid.")
    parser.add_argument("--results-root", type=Path,
                        default=Path("strategies/strategy_04/v1_2/results"))
    args = parser.parse_args()

    grid: dict[str, dict[str, dict[str, object]]] = {}
    for symbol in SYMBOLS:
        grid[symbol] = {}
        for variant in VARIANTS:
            report_path = (args.results_root / f"{symbol.lower()}_1h_15m_{variant}"
                           / "backtest_report.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            fixed = report["results"]["fixed"]
            grid[symbol][variant] = {
                "candidates": report["candidate_signal_count"],
                "trades": fixed["trade_count"],
                "win_rate": fixed["win_rate"],
                "average_r": fixed["average_r"],
                "net_pnl": fixed["net_pnl"],
            }

    (args.results_root / "ablation.json").write_text(
        json.dumps(grid, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Strategy 04 v1.2 ablation -- fixed 0.15% risk",
        "",
        "Every number is in-sample. Per the spec, a filter that helps one",
        "symbol must not be adopted for others without its own evidence, and",
        "promotion additionally requires out-of-sample confirmation, parameter",
        "sensitivity, and cost stress. This table attributes effects; it does",
        "not approve anything.",
        "",
    ]
    for symbol, variants in grid.items():
        base = variants["base"]
        lines += [
            f"## {symbol}",
            "",
            "| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for variant, row in variants.items():
            delta = row["net_pnl"] - base["net_pnl"]
            lines.append(
                f"| {variant} | {row['candidates']} | {row['trades']} "
                f"| {row['win_rate']:.3f} | {row['average_r']:+.4f} "
                f"| {row['net_pnl']:+.2f} | {delta:+.2f} |"
            )
        lines.append("")
    (args.results_root / "ABLATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved ablation summary to {args.results_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
