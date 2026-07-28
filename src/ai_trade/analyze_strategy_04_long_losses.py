"""Summarize diagnostic thresholds for Strategy 04 v1 long trades.

This module reads the deterministic diagnostic CSV produced by
``review_strategy_04_long_losses`` and prints compact win/loss comparisons.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_INPUT = Path(
    "strategies/strategy_04/v1/results/spy_1h_15m/review/long_losses/"
    "all_long_diagnostics.csv"
)

THRESHOLDS = (
    ("penetration <= 0.25 zone", "zone_penetration_fraction", "le", 0.25),
    ("penetration > 0.25 zone", "zone_penetration_fraction", "gt", 0.25),
    ("penetration > 0.50 zone", "zone_penetration_fraction", "gt", 0.50),
    ("trigger range <= 0.60 ATR", "trigger_range_atr", "le", 0.60),
    ("trigger range > 0.60 ATR", "trigger_range_atr", "gt", 0.60),
    ("entry extension <= 0.25 ATR", "entry_extension_atr", "le", 0.25),
    ("entry extension > 0.25 ATR", "entry_extension_atr", "gt", 0.25),
)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for name, key, comparison, threshold in THRESHOLDS:
        if comparison == "le":
            group = [row for row in rows if float(row[key]) <= threshold]
        else:
            group = [row for row in rows if float(row[key]) > threshold]
        wins = sum(row["outcome"] == "win" for row in group)
        losses = sum(row["outcome"] == "loss" for row in group)
        output.append(
            {
                "group": name,
                "trades": len(group),
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(100.0 * wins / len(group), 1) if group else None,
            }
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    print("group,trades,wins,losses,win_rate_pct")
    for row in summarize(load_rows(args.input)):
        rate = "NA" if row["win_rate_pct"] is None else f"{row['win_rate_pct']:.1f}"
        print(
            f"{row['group']},{row['trades']},{row['wins']},"
            f"{row['losses']},{rate}"
        )


if __name__ == "__main__":
    main()
