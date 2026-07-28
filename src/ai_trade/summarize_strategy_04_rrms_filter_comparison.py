"""Compare Strategy 04 v1 and v1.1 under both RRMS reset policies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _five(report: dict[str, object]) -> dict[str, object]:
    return report["results"]["rrms"]


def _four(report: dict[str, object]) -> dict[str, object]:
    return report["results"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1-five", nargs="+", type=Path, required=True)
    parser.add_argument("--v1-four", nargs="+", type=Path, required=True)
    parser.add_argument("--v11-five", nargs="+", type=Path, required=True)
    parser.add_argument("--v11-four", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    v1_five = {_load(path)["symbol"]: _five(_load(path)) for path in args.v1_five}
    v1_four = {_load(path)["symbol"]: _four(_load(path)) for path in args.v1_four}
    v11_five = {_load(path)["symbol"]: _five(_load(path)) for path in args.v11_five}
    v11_four = {_load(path)["symbol"]: _four(_load(path)) for path in args.v11_four}
    symbols = sorted(set(v1_five) & set(v1_four) & set(v11_five) & set(v11_four))
    rows = [
        {
            "symbol": symbol,
            "v1_five": v1_five[symbol],
            "v1_four": v1_four[symbol],
            "v11_five": v11_five[symbol],
            "v11_four": v11_four[symbol],
        }
        for symbol in symbols
    ]

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "rrms_filter_comparison.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Strategy 04 — RRMS comparison by strategy version",
        "",
        "Five-loss RRMS allows a fifth 1.50% loss. Four-loss RRMS resets the trade after the fourth negative exit to 0.15%.",
        "",
        "| Symbol | v1 five-loss | v1.1 five-loss | v1.1 minus v1 | v1 four-loss | v1.1 four-loss | v1.1 minus v1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        v1_5, v1_4 = row["v1_five"], row["v1_four"]
        v11_5, v11_4 = row["v11_five"], row["v11_four"]
        lines.append(
            f"| {row['symbol']} | ${v1_5['net_pnl']:,.2f} | ${v11_5['net_pnl']:,.2f} | "
            f"${v11_5['net_pnl'] - v1_5['net_pnl']:+,.2f} | ${v1_4['net_pnl']:,.2f} | "
            f"${v11_4['net_pnl']:,.2f} | ${v11_4['net_pnl'] - v1_4['net_pnl']:+,.2f} |"
        )
    lines.extend(
        [
            "",
            "## Drawdown under the four-loss policy",
            "",
            "| Symbol | v1 four-loss DD | v1.1 four-loss DD |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['symbol']} | ${row['v1_four']['max_drawdown']:,.2f} | "
            f"${row['v11_four']['max_drawdown']:,.2f} |"
        )
    lines.extend(
        [
            "",
            "RRMS results are path-dependent. They should be assessed only after a fixed-risk edge is accepted for that exact symbol and version.",
            "",
        ]
    )
    (args.output / "RRMS_FILTER_COMPARISON.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
