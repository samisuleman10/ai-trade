"""Standard post-backtest workflow: fixed/RRMS summary plus trade charts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from ai_trade.render_trade_review_batch import render_batch


ROOT = Path(__file__).resolve().parents[2]


def _money(value: object) -> str:
    return f"${float(value):+,.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the standard fixed/RRMS strategy review package.")
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
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = render_batch(args.bars, args.fixed_trades, args.output / "trade_charts", args.chart_count)

    generator = ROOT / "scripts" / "generate_trade_review_visual.py"
    for mode, ledger in (("fixed", args.fixed_trades), ("rrms", args.rrms_trades)):
        subprocess.run([
            sys.executable, str(generator), "--bars", str(args.bars), "--trades", str(ledger),
            "--output", str(args.output / f"{mode}_trade_review.html"), "--symbol", args.symbol,
            "--timeframe", args.timeframe, "--review-id", f"{args.symbol.lower()}-{args.timeframe}-{mode}-review",
        ], cwd=ROOT, check=True)

    summary = f"""# Standard strategy review — {args.symbol} {args.timeframe}

| Sizing | Trades | Win rate | Net P&L | Profit factor | Average R | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Fixed 0.15% | {fixed['trade_count']} | {float(fixed['win_rate'] or 0):.1%} | {_money(fixed['net_pnl'])} | {float(fixed['profit_factor'] or 0):.2f} | {float(fixed['average_r'] or 0):+.3f} | ${float(fixed['max_drawdown']):,.2f} |
| RRMS | {rrms['trade_count']} | {float(rrms['win_rate'] or 0):.1%} | {_money(rrms['net_pnl'])} | {float(rrms['profit_factor'] or 0):.2f} | {float(rrms['average_r'] or 0):+.3f} | ${float(rrms['max_drawdown']):,.2f} |

The saved chart sample covers trades {', '.join(map(str, manifest['selected_trade_numbers']))} from the fixed-risk ledger. Fixed and RRMS use the same entry, stop, target, and exit paths; RRMS changes position sizing and may stop after its maximum loss tier.
"""
    (args.output / "review_summary.md").write_text(summary, encoding="utf-8")
    workflow_manifest = {
        "report": str(args.report), "bars": str(args.bars),
        "fixed_trades": str(args.fixed_trades), "rrms_trades": str(args.rrms_trades),
        "review_summary": str(args.output / "review_summary.md"),
        "fixed_interactive_review": str(args.output / "fixed_trade_review.html"),
        "rrms_interactive_review": str(args.output / "rrms_trade_review.html"),
        "chart_sample": manifest,
    }
    (args.output / "workflow_manifest.json").write_text(json.dumps(workflow_manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved standard review workflow to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
