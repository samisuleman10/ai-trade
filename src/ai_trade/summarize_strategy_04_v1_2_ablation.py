"""Cross-variant ablation table for Strategy 04 v1.2.

Reads the twenty committed backtest reports (5 symbols x 4 variants) and
writes one comparison table so filter effects can be attributed per symbol,
per the spec's required ablation. Interpretation stays with the human: the
spec's promotion criteria require out-of-sample confirmation and sensitivity
evidence that this table alone cannot provide.

Every symbol's four variants must share one ``max_risk_zone_ratio`` (Filter
A's in-sample, unvalidated threshold -- see the Research warning in
strategy.md and the sweep in results/sweep/SWEEP.md); a mismatch means a
partial re-run mixed thresholds and is reported as an error rather than
silently summarized.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SYMBOLS = ("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD")
VARIANTS = ("base", "a", "b", "ab")
_FX_SYMBOLS = ("EURUSD", "GBPUSD")


def _format_metric(value: object, spec: str) -> str:
    return "n/a" if value is None else format(value, spec)


def build_grid(results_root: Path) -> dict[str, dict[str, object]]:
    """Load the twenty reports into {symbol: {max_risk_zone_ratio, variants}}."""
    grid: dict[str, dict[str, object]] = {}
    for symbol in SYMBOLS:
        variants: dict[str, dict[str, object]] = {}
        thresholds: dict[str, float] = {}
        for variant in VARIANTS:
            report_path = (results_root / f"{symbol.lower()}_1h_15m_{variant}"
                           / "backtest_report.json")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            fixed = report["results"]["fixed"]
            thresholds[variant] = report["execution_parameters"]["max_risk_zone_ratio"]
            variants[variant] = {
                "candidates": report["candidate_signal_count"],
                "trades": fixed["trade_count"],
                "win_rate": fixed["win_rate"],
                "average_r": fixed["average_r"],
                "net_pnl": fixed["net_pnl"],
            }
        distinct = set(thresholds.values())
        if len(distinct) != 1:
            raise ValueError(
                f"{symbol}: max_risk_zone_ratio differs across variants "
                f"(guards against a mixed-threshold partial re-run): {thresholds}"
            )
        grid[symbol] = {
            "max_risk_zone_ratio": distinct.pop(),
            "variants": variants,
        }
    return grid


def render_markdown(grid: dict[str, dict[str, object]]) -> str:
    thresholds = {symbol: data["max_risk_zone_ratio"] for symbol, data in grid.items()}
    distinct_thresholds = set(thresholds.values())
    if len(distinct_thresholds) == 1:
        threshold_value = distinct_thresholds.pop()
        threshold_sentence = (
            f"Filter A rows use max_risk_zone_ratio = {threshold_value:g}, an "
            "in-sample, unvalidated threshold -- see the sweep."
        )
    else:
        per_symbol = ", ".join(f"{symbol}={value:g}" for symbol, value in thresholds.items())
        threshold_sentence = (
            f"Filter A rows use max_risk_zone_ratio per symbol ({per_symbol}), an "
            "in-sample, unvalidated threshold -- see the sweep."
        )
    fx_sentence = (
        "FX rows (EURUSD/GBPUSD) are TPO-zone, midpoint-data, modelled-spread "
        "runs with equity-tuned bar-count windows and are not comparable 1:1 "
        "with equity rows."
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
        threshold_sentence,
        "",
        fx_sentence,
        "",
    ]
    for symbol, data in grid.items():
        variants = data["variants"]
        base = variants["base"]
        lines += [
            f"## {symbol}",
            "",
            "| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for variant, row in variants.items():
            delta = row["net_pnl"] - base["net_pnl"]
            win_rate_str = _format_metric(row["win_rate"], ".3f")
            average_r_str = _format_metric(row["average_r"], "+.4f")
            lines.append(
                f"| {variant} | {row['candidates']} | {row['trades']} "
                f"| {win_rate_str} | {average_r_str} "
                f"| {row['net_pnl']:+.2f} | {delta:+.2f} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the v1.2 ablation grid.")
    parser.add_argument("--results-root", type=Path,
                        default=Path("strategies/strategy_04/v1_2/results"))
    args = parser.parse_args()

    grid = build_grid(args.results_root)

    (args.results_root / "ablation.json").write_text(
        json.dumps(grid, indent=2) + "\n", encoding="utf-8"
    )
    (args.results_root / "ABLATION.md").write_text(render_markdown(grid), encoding="utf-8")
    print(f"Saved ablation summary to {args.results_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
