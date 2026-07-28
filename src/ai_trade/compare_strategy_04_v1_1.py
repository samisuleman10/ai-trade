"""Save a deterministic Strategy 04 v1 versus v1.1 comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _row(report: dict[str, object], mode: str, side: str | None) -> dict[str, float]:
    result = report["results"][mode]
    source = result if side is None else result["details"][side]
    return {
        "trades": int(source["trade_count"] if side is None else source["trades"]),
        "wins": int(source["wins"]),
        "losses": int(source["losses"]),
        "win_rate": float(source["win_rate"]),
        "net_pnl": float(source["net_pnl"]),
        "average_r": float(source["average_r"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("strategies/strategy_04/v1/results/spy_1h_15m/backtest_report.json"),
    )
    parser.add_argument(
        "--variant",
        type=Path,
        default=Path("strategies/strategy_04/v1_1/results/spy_1h_15m/backtest_report.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("strategies/strategy_04/v1_1/results/spy_1h_15m"),
    )
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    variant = json.loads(args.variant.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for mode in ("fixed", "rrms"):
        for side in (None, "long", "short"):
            old = _row(baseline, mode, side)
            new = _row(variant, mode, side)
            rows.append(
                {
                    "mode": mode,
                    "scope": side or "all",
                    "v1": old,
                    "v1_1": new,
                    "delta": {
                        "trades": new["trades"] - old["trades"],
                        "win_rate": new["win_rate"] - old["win_rate"],
                        "net_pnl": new["net_pnl"] - old["net_pnl"],
                        "average_r": new["average_r"] - old["average_r"],
                    },
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    payload = {
        "baseline": str(args.baseline),
        "variant": str(args.variant),
        "single_change": "long demand-zone penetration <= 25%",
        "rows": rows,
    }
    (args.output / "comparison_v1_vs_v1_1.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Strategy 04: v1 versus v1.1",
        "",
        "Version 1.1 changes only the long trigger: its low may penetrate no more than 25% of the demand-zone width.",
        "",
        "| Sizing | Scope | v1 trades | v1 win rate | v1 P&L | v1.1 trades | v1.1 win rate | v1.1 P&L | P&L change |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows:
        old, new, delta = item["v1"], item["v1_1"], item["delta"]
        lines.append(
            f"| {item['mode']} | {item['scope']} | {old['trades']} | "
            f"{100 * old['win_rate']:.1f}% | ${old['net_pnl']:,.2f} | "
            f"{new['trades']} | {100 * new['win_rate']:.1f}% | "
            f"${new['net_pnl']:,.2f} | ${delta['net_pnl']:+,.2f} |"
        )
    lines.extend(
        [
            "",
            "## Validation warning",
            "",
            "The penetration threshold was discovered from this same historical sample. Improvement here is in-sample evidence, not proof of generalization. Preserve v1 as the baseline and validate v1.1 on unseen data before promotion.",
            "",
        ]
    )
    (args.output / "COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
