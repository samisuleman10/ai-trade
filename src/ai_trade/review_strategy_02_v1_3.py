"""Create deterministic historical-review data for Strategy 02 v1.3."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.strategy_01 import alligator_points, load_ohlcv_csv
from ai_trade.strategy_02_v1 import _heikin_ashi
from ai_trade.strategy_02_v1_3 import candidate_signals, hourly_structure_points


def _row(bar, ha, alligator, structure=None):
    result = {
        "t": bar.timestamp,
        "o": round(ha[0], 4), "h": round(ha[1], 4),
        "l": round(ha[2], 4), "c": round(ha[3], 4),
        "jaw": None if alligator.jaw is None else round(alligator.jaw, 4),
        "teeth": None if alligator.teeth is None else round(alligator.teeth, 4),
        "lips": None if alligator.lips is None else round(alligator.lips, 4),
    }
    if structure is not None:
        result.update({
            "support": None if structure.support is None else round(structure.support, 4),
            "resistance": None if structure.resistance is None else round(structure.resistance, 4),
        })
    return result


def build_review(fifteen_path: Path, hourly_path: Path) -> dict[str, object]:
    fifteen, hourly = load_ohlcv_csv(fifteen_path), load_ohlcv_csv(hourly_path)
    signals = candidate_signals(fifteen, hourly)
    chosen_dates = {
        "2023-01-20T15:30:00Z", "2024-11-05T14:45:00Z",
        "2022-09-13T13:45:00Z", "2024-09-24T14:15:00Z",
    }
    chosen = [signal for signal in signals if signal["entry_timestamp"] in chosen_dates]
    h_ha, f_ha = _heikin_ashi(hourly), _heikin_ashi(fifteen)
    h_alligator, f_alligator = alligator_points(hourly), alligator_points(fifteen)
    h_structure = hourly_structure_points(hourly)
    h_index = {bar.timestamp: i for i, bar in enumerate(hourly)}
    f_index = {bar.timestamp: i for i, bar in enumerate(fifteen)}
    examples = []
    for signal in chosen:
        hi = h_index[signal["structure_pivot_timestamp"]]
        fi = f_index[signal["entry_timestamp"]]
        h_start, h_end = max(0, hi - 12), min(len(hourly), hi + 18)
        f_start, f_end = max(0, fi - 14), min(len(fifteen), fi + 15)
        examples.append({
            "signal": signal,
            "hourly": [_row(hourly[i], h_ha[i], h_alligator[i], h_structure[i]) for i in range(h_start, h_end)],
            "fifteen": [_row(fifteen[i], f_ha[i], f_alligator[i]) for i in range(f_start, f_end)],
        })
    return {
        "period": {"start": fifteen[0].timestamp, "end": fifteen[-1].timestamp},
        "candidate_count": len(signals),
        "long_count": sum(s["side"] == "long" for s in signals),
        "short_count": sum(s["side"] == "short" for s in signals),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fifteen", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"))
    parser.add_argument("--hourly", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"))
    parser.add_argument("--output", type=Path, default=Path("strategies/strategy_02/v1_3/results/historical_review.json"))
    args = parser.parse_args()
    review = build_review(args.fifteen, args.hourly)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(review['examples'])} examples from {review['candidate_count']} candidates to {args.output}")


if __name__ == "__main__":
    main()
