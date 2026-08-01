"""Does Strategy 01's entry inherit the Strategy 03 Alligator falsification?

Strategy 01 v1/v2/v4/v5 enter on a 15-minute Alligator mouth-opening, gated by
two extra conditions Strategy 03 does not have:

  1. the 1-hour Alligator is open and agrees with the trade direction, and
  2. the completed 15-minute Heikin Ashi body sits entirely beyond the Lips.

Strategy 03's recorded 15-minute trades already tell us what the ungated entry
is worth. This script re-labels those same trades with conditions (1) and (2)
-- using Strategy 01's own definitions, imported from `ai_trade.strategy_01` --
and reports what the gated subset earns.

This is a mechanism test on already-recorded trades, not a Strategy 01
backtest. It asks one question: do Strategy 01's extra filters rescue an entry
that loses without them?

Usage:
    python scripts/analyze_strategy_01_inheritance.py --data-root <dir>

The bar cache is gitignored, so --data-root must point at a local
data/market_data/ibkr directory.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_trade.strategy_01 import alligator_points, load_ohlcv_csv  # noqa: E402

# ledger directory -> (15m bars, 1h bars), relative to --data-root
INSTRUMENTS: list[tuple[str, str, str]] = [
    ("spy_15m", "SPY/v4_2y/spy_15m.csv", "SPY/v4_2y/spy_1h.csv"),
    ("qqq_15m", "QQQ/v5_5y/qqq_15m.csv", "QQQ/v5_5y/qqq_1h.csv"),
    ("us30_dia_15m", "US30_DIA/v5_5y/dia_15m.csv", "US30_DIA/v5_5y/dia_1h.csv"),
    ("iwm_15m", "IWM/v5_5y/iwm_15m.csv", "IWM/v5_5y/iwm_1h.csv"),
    ("gld_15m", "GLD/v5_5y/gld_15m.csv", "GLD/v5_5y/gld_1h.csv"),
    ("slv_15m", "SLV/v5_5y/slv_15m.csv", "SLV/v5_5y/slv_1h.csv"),
    ("eurusd_15m", "EURUSD/v1_5y/eurusd_15m.csv", "EURUSD/v1_5y/eurusd_1h.csv"),
    ("gbpusd_15m", "GBPUSD/v1_5y/gbpusd_15m.csv", "GBPUSD/v1_5y/gbpusd_1h.csv"),
]

LEDGER_ROOT = REPO_ROOT / "strategies" / "strategy_03" / "v1" / "results"
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)


def mean_and_t(values: list[float]) -> tuple[int, float, float]:
    """Return (n, mean, t) for a one-sample t-test against zero."""
    n = len(values)
    if n < 2:
        return n, (values[0] if values else float("nan")), float("nan")
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    if variance <= 0:
        return n, mean, float("nan")
    return n, mean, mean / math.sqrt(variance / n)


def label_trades(ledger: Path, bars_15m: Path, bars_1h: Path, *, use_prior_bar: bool):
    """Attach Strategy 01's two extra conditions to Strategy 03's trades."""
    entry_bars = load_ohlcv_csv(bars_15m)
    entry_points = alligator_points(entry_bars)
    index_by_stamp = {bar.timestamp: i for i, bar in enumerate(entry_bars)}

    trend_points = alligator_points(load_ohlcv_csv(bars_1h))
    # A 1-hour bar only counts once it has closed.
    trend_closes = sorted(
        (parse(p.timestamp) + timedelta(hours=1), p) for p in trend_points
    )

    def trend_state_at(when: datetime):
        chosen = None
        for close_time, point in trend_closes:
            if close_time <= when:
                chosen = point
            else:
                break
        return chosen

    rows = []
    unmatched = 0
    with ledger.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stamp = row["decision_timestamp"]
            if stamp not in index_by_stamp:
                unmatched += 1
                continue
            index = index_by_stamp[stamp]
            # The completed bar creates the signal; entry is the next bar open.
            signal_index = index - 1 if use_prior_bar else index
            if signal_index < 0:
                unmatched += 1
                continue
            point = entry_points[signal_index]
            if point.lips is None:
                unmatched += 1
                continue

            long_side = row["side"].strip().lower() == "long"
            if long_side:
                ha_ok = min(point.ha_open, point.ha_close) > point.lips
            else:
                ha_ok = max(point.ha_open, point.ha_close) < point.lips

            signal_close = parse(entry_bars[signal_index].timestamp) + timedelta(minutes=15)
            trend = trend_state_at(signal_close)
            if trend is None:
                htf_ok = False
            else:
                htf_ok = trend.bullish_open if long_side else trend.bearish_open

            rows.append((float(row["result_r"]), ha_ok, bool(htf_ok)))
    return rows, unmatched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args()

    for use_prior_bar in (True, False):
        convention = "signal = bar BEFORE decision_timestamp" if use_prior_bar else "signal = decision bar itself"
        print(f"\n{'=' * 78}\nConvention: {convention}\n{'=' * 78}")
        print(f"{'instrument':<14}{'all n':>7}{'all R':>9}{'all t':>8}"
              f"{'S01 n':>8}{'S01 R':>9}{'S01 t':>8}")

        pooled_all: list[float] = []
        pooled_s01: list[float] = []
        total_unmatched = 0

        for ledger_dir, rel_15m, rel_1h in INSTRUMENTS:
            ledger = LEDGER_ROOT / ledger_dir / "fixed_trades.csv"
            bars_15m = args.data_root / rel_15m
            bars_1h = args.data_root / rel_1h
            if not ledger.exists() or not bars_15m.exists() or not bars_1h.exists():
                print(f"{ledger_dir:<14}  SKIPPED (missing ledger or bars)")
                continue

            rows, unmatched = label_trades(ledger, bars_15m, bars_1h, use_prior_bar=use_prior_bar)
            total_unmatched += unmatched
            every = [r for r, _, _ in rows]
            # Strategy 01's entry = both extra conditions satisfied.
            s01 = [r for r, ha_ok, htf_ok in rows if ha_ok and htf_ok]
            pooled_all += every
            pooled_s01 += s01

            n_a, m_a, t_a = mean_and_t(every)
            n_s, m_s, t_s = mean_and_t(s01)
            print(f"{ledger_dir:<14}{n_a:>7}{m_a:>9.4f}{t_a:>8.2f}"
                  f"{n_s:>8}{m_s:>9.4f}{t_s:>8.2f}")

        n_a, m_a, t_a = mean_and_t(pooled_all)
        n_s, m_s, t_s = mean_and_t(pooled_s01)
        print(f"{'POOLED':<14}{n_a:>7}{m_a:>9.4f}{t_a:>8.2f}"
              f"{n_s:>8}{m_s:>9.4f}{t_s:>8.2f}")
        print(f"unmatched/skipped trades: {total_unmatched}")
        if n_a:
            print(f"Strategy 01 gate retains {100 * n_s / n_a:.1f}% of Strategy 03's trades")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
