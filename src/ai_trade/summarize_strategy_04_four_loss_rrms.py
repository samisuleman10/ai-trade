"""Compare five-loss and four-loss RRMS runs for Strategy 04 v1.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--five-loss", nargs="+", type=Path, required=True)
    parser.add_argument("--four-loss", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    five = [_read(path) for path in args.five_loss]
    four = [_read(path) for path in args.four_loss]
    by_symbol = {item["symbol"]: item for item in four}

    rows = []
    for old in five:
        new = by_symbol[old["symbol"]]
        old_result, new_result = old["results"]["rrms"], new["results"]
        rows.append(
            {
                "symbol": old["symbol"],
                "five_loss": old_result,
                "four_loss": new_result,
                "net_pnl_change": new_result["net_pnl"] - old_result["net_pnl"],
                "drawdown_change": new_result["max_drawdown"] - old_result["max_drawdown"],
            }
        )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "four_loss_rrms_comparison.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Strategy 04 v1.1 — RRMS reset after the fourth loss",
        "",
        "Four-loss tiers: 0.15%, 0.35%, 0.70%, 1.50%. After the fourth negative exit, the next trade resets to 0.15%.",
        "",
        "| Symbol | Five-loss P&L | Four-loss P&L | P&L change | Five-loss DD | Four-loss DD | DD change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        old, new = row["five_loss"], row["four_loss"]
        lines.append(
            f"| {row['symbol']} | ${old['net_pnl']:,.2f} | ${new['net_pnl']:,.2f} | "
            f"${row['net_pnl_change']:+,.2f} | ${old['max_drawdown']:,.2f} | "
            f"${new['max_drawdown']:,.2f} | ${row['drawdown_change']:+,.2f} |"
        )
    lines.append("")
    (args.output / "FOUR_LOSS_RRMS_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
