"""Create a compact cross-market report for Strategy 04 v1.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _metrics(report: dict[str, object], mode: str) -> dict[str, float]:
    result = report["results"][mode]
    return {
        "trades": int(result["trade_count"]),
        "wins": int(result["wins"]),
        "losses": int(result["losses"]),
        "win_rate": float(result["win_rate"]),
        "net_pnl": float(result["net_pnl"]),
        "profit_factor": float(result["profit_factor"]),
        "average_r": float(result["average_r"]),
        "max_drawdown": float(result["max_drawdown"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reports",
        nargs="+",
        type=Path,
        required=True,
        help="One or more backtest_report.json paths.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records: list[dict[str, object]] = []
    for path in args.reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        records.append(
            {
                "symbol": report["symbol"],
                "data": report["data"],
                "candidate_signals": report["candidate_signal_count"],
                "eligible_signals": report["session_eligible_signal_count"],
                "fixed": _metrics(report, "fixed"),
                "rrms": _metrics(report, "rrms"),
                "report": str(path),
            }
        )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "cross_market_summary.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Strategy 04 v1.1 — cross-market cached-data test",
        "",
        "The 25% long-zone penetration threshold is unchanged across every symbol.",
        "",
        "## Fixed 0.15% risk",
        "",
        "| Symbol | Period | Trades | Win rate | Net P&L | PF | Avg R | Max DD |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in records:
        metric, data = item["fixed"], item["data"]
        lines.append(
            f"| {item['symbol']} | {data['fifteen_minute_first'][:10]} to "
            f"{data['fifteen_minute_last'][:10]} | {metric['trades']} | "
            f"{100 * metric['win_rate']:.1f}% | ${metric['net_pnl']:,.2f} | "
            f"{metric['profit_factor']:.2f} | {metric['average_r']:.3f} | "
            f"${metric['max_drawdown']:,.2f} |"
        )
    lines.extend(
        [
            "",
            "## Five-loss RRMS",
            "",
            "| Symbol | Trades | Win rate | Net P&L | PF | Avg R | Max DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in records:
        metric = item["rrms"]
        lines.append(
            f"| {item['symbol']} | {metric['trades']} | {100 * metric['win_rate']:.1f}% | "
            f"${metric['net_pnl']:,.2f} | {metric['profit_factor']:.2f} | "
            f"{metric['average_r']:.3f} | ${metric['max_drawdown']:,.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "QQQ and DIA are out-of-symbol checks, not independent macro regimes: they are correlated US equity-index ETFs. Positive results on both would strengthen confidence that the rule is not SPY-only, but they do not prove generalization. Futures require their own contract multiplier, cost, and session model.",
            "",
        ]
    )
    (args.output / "CROSS_MARKET_VALIDATION.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
