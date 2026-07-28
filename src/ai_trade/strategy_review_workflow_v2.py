"""Standard strategy review v2: fixed/RRMS detail and visual trade audit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ai_trade.render_trade_review_batch import render_batch
from ai_trade.trade_statistics import ledger_statistics


ROOT = Path(__file__).resolve().parents[2]


def _money(value: object) -> str:
    return f"${float(value):+,.2f}"


def _detail_row(label: str, summary: dict[str, object], detail: dict[str, object]) -> str:
    long, short = detail["long"], detail["short"]
    weekend, stop, target = detail["weekend_close"], detail["stop"], detail["target"]
    return (
        f"| {label} | {summary['trade_count']} | {detail['wins']}/{detail['losses']} | "
        f"{long['wins']}/{long['losses']} | {short['wins']}/{short['losses']} | "
        f"{weekend['trades']} ({weekend['wins']}/{weekend['losses']}) | "
        f"{stop['trades']} / {target['trades']} | {_money(summary['net_pnl'])} | "
        f"{float(summary['profit_factor'] or 0):.2f} | {float(summary['average_r'] or 0):+.3f} | "
        f"${float(summary['max_drawdown']):,.2f} | {detail['maximum_consecutive_losses']} |"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the detailed fixed/RRMS strategy review package.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--fixed-trades", type=Path, required=True)
    parser.add_argument("--rrms-trades", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--chart-count", type=int, default=10)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    fixed, rrms = report["results"]["fixed"], report["results"]["rrms"]
    fixed_detail, rrms_detail = ledger_statistics(args.fixed_trades), ledger_statistics(args.rrms_trades)
    args.output.mkdir(parents=True, exist_ok=True)
    charts = render_batch(args.bars, args.fixed_trades, args.output / "trade_charts", args.chart_count)

    generator = ROOT / "scripts" / "generate_trade_review_visual.py"
    for mode, ledger in (("fixed", args.fixed_trades), ("rrms", args.rrms_trades)):
        subprocess.run([
            sys.executable, str(generator), "--bars", str(args.bars), "--trades", str(ledger),
            "--output", str(args.output / f"{mode}_trade_review.html"), "--symbol", args.symbol,
            "--timeframe", args.timeframe, "--review-id", f"{args.symbol.lower()}-{args.timeframe}-{mode}-review",
        ], cwd=ROOT, check=True)

    header = "| Sizing | Trades | W/L | Long W/L | Short W/L | Weekend exits (W/L) | Stop / target | Net P&L | PF | Avg R | Max DD | Max loss streak |"
    divider = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    summary = "\n".join([
        f"# Detailed strategy review — {args.symbol} {args.timeframe}", "", header, divider,
        _detail_row("Fixed 0.15%", fixed, fixed_detail), _detail_row("RRMS", rrms, rrms_detail), "",
        f"Average holding time: fixed {float(fixed_detail['average_holding_hours'] or 0):.1f} hours; RRMS {float(rrms_detail['average_holding_hours'] or 0):.1f} hours. Maximum RRMS tier reached: {rrms_detail['maximum_rrms_tier']}.", "",
        f"The saved chart sample covers trades {', '.join(map(str, charts['selected_trade_numbers']))}. Fixed and RRMS use the same price setup; RRMS changes position size and can terminate after its maximum loss tier.", "",
    ])
    (args.output / "review_summary_detailed.md").write_text(summary, encoding="utf-8")
    manifest = {
        "report": str(args.report), "bars": str(args.bars),
        "fixed_trades": str(args.fixed_trades), "rrms_trades": str(args.rrms_trades),
        "fixed_statistics": fixed_detail, "rrms_statistics": rrms_detail,
        "trade_charts": charts,
        "fixed_interactive_review": str(args.output / "fixed_trade_review.html"),
        "rrms_interactive_review": str(args.output / "rrms_trade_review.html"),
    }
    (args.output / "workflow_manifest_detailed.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved detailed strategy review to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
