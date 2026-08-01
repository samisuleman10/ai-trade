"""Does Strategy 01's entry inherit the Strategy 03 Alligator falsification?

Strategy 01 gates an Alligator mouth-opening entry with two conditions
Strategy 03 does not have:

  1. the higher timeframe Alligator is open and agrees with the direction, and
  2. the completed entry-timeframe Heikin Ashi body sits entirely beyond the
     Lips.

Two bands are tested, because the versions do not share one:

  * ``--band 15m`` — v1, v2, v4, v5: 1h confirmation, 15m entry.
  * ``--band 1h``  — v3:             4h confirmation, 1h entry.

Strategy 03's recorded trades already say what the ungated entry is worth.
This script re-labels those same trades with conditions (1) and (2), using
Strategy 01's own definitions imported from `ai_trade.strategy_01` rather than
reimplemented, and reports what the gated subset earns.

This is a mechanism test on already-recorded trades, not a Strategy 01
backtest. It asks one question: do Strategy 01's extra filters rescue an entry
that loses without them?

Usage:
    python scripts/analyze_strategy_01_inheritance.py --data-root <dir> [--band 15m|1h|both]

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

# (ledger dir, entry bars, trend bars) relative to --data-root
BANDS: dict[str, dict] = {
    # v1, v2, v4, v5 — 1h confirmation over a 15m entry.
    "15m": {
        "entry_minutes": 15,
        "trend_minutes": 60,
        "versions": "v1, v2, v4, v5",
        "instruments": [
            ("spy_15m", "SPY/v4_2y/spy_15m.csv", "SPY/v4_2y/spy_1h.csv"),
            ("qqq_15m", "QQQ/v5_5y/qqq_15m.csv", "QQQ/v5_5y/qqq_1h.csv"),
            ("us30_dia_15m", "US30_DIA/v5_5y/dia_15m.csv", "US30_DIA/v5_5y/dia_1h.csv"),
            ("iwm_15m", "IWM/v5_5y/iwm_15m.csv", "IWM/v5_5y/iwm_1h.csv"),
            ("gld_15m", "GLD/v5_5y/gld_15m.csv", "GLD/v5_5y/gld_1h.csv"),
            ("slv_15m", "SLV/v5_5y/slv_15m.csv", "SLV/v5_5y/slv_1h.csv"),
            ("eurusd_15m", "EURUSD/v1_5y/eurusd_15m.csv", "EURUSD/v1_5y/eurusd_1h.csv"),
            ("gbpusd_15m", "GBPUSD/v1_5y/gbpusd_15m.csv", "GBPUSD/v1_5y/gbpusd_1h.csv"),
        ],
    },
    # v3 — 4h confirmation over a 1h entry. Only three instruments have a 1h
    # ledger, and SPY's 4h cache is two years against a five-year ledger.
    "1h": {
        "entry_minutes": 60,
        "trend_minutes": 240,
        "versions": "v3",
        "instruments": [
            ("spy_1h", "SPY/v4_2y/spy_1h.csv", "SPY/spy_4h.csv"),
            ("qqq_1h", "QQQ/v5_5y/qqq_1h.csv", "QQQ/v5_5y/qqq_4h.csv"),
            ("us30_dia_1h", "US30_DIA/v5_5y/dia_1h.csv", "US30_DIA/v5_5y/dia_4h.csv"),
        ],
    },
}

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


def trend_close_times(points, nominal: timedelta) -> list[tuple[datetime, object]]:
    """Close time of each trend bar.

    A session-truncated bar closes when the next one opens; the last bar of a
    session closes a nominal duration after it opened. Taking the minimum
    handles both without special-casing the calendar.
    """
    starts = [parse(p.timestamp) for p in points]
    closes = []
    for index, point in enumerate(points):
        close = starts[index] + nominal
        if index + 1 < len(starts):
            close = min(close, starts[index + 1])
        closes.append((close, point))
    return sorted(closes, key=lambda pair: pair[0])


def label_trades(ledger: Path, entry_csv: Path, trend_csv: Path, *,
                 entry_minutes: int, trend_minutes: int, use_prior_bar: bool):
    """Attach Strategy 01's two extra conditions to Strategy 03's trades.

    Returns (rows, unmatched) where each row is
    (result_r, ha_ok, htf_ok, trend_data_available).
    """
    entry_bars = load_ohlcv_csv(entry_csv)
    entry_points = alligator_points(entry_bars)
    index_by_stamp = {bar.timestamp: i for i, bar in enumerate(entry_bars)}

    trend_points = alligator_points(load_ohlcv_csv(trend_csv))
    closes = trend_close_times(trend_points, timedelta(minutes=trend_minutes))
    # A trend point is only usable once its own Alligator has warmed up.
    first_usable = next(
        (close for close, point in closes if point.lips is not None), None
    )

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

            signal_close = parse(entry_bars[signal_index].timestamp) + timedelta(minutes=entry_minutes)
            covered = first_usable is not None and signal_close >= first_usable

            trend = None
            for close, candidate in closes:
                if close <= signal_close and candidate.lips is not None:
                    trend = candidate
                elif close > signal_close:
                    break
            if trend is None:
                htf_ok = False
            else:
                htf_ok = trend.bullish_open if long_side else trend.bearish_open

            rows.append((float(row["result_r"]), ha_ok, bool(htf_ok), covered))
    return rows, unmatched


def run_band(band: str, data_root: Path) -> None:
    config = BANDS[band]
    print(f"\n{'#' * 78}")
    print(f"# Band {band}  (Strategy 01 {config['versions']}) — "
          f"{config['trend_minutes']}m confirmation over {config['entry_minutes']}m entry")
    print("#" * 78)

    for use_prior_bar in (True, False):
        convention = "bar BEFORE decision_timestamp" if use_prior_bar else "decision bar itself"
        print(f"\nConvention: signal = {convention}")
        print(f"{'instrument':<14}{'cov n':>7}{'cov R':>9}{'cov t':>8}"
              f"{'S01 n':>8}{'S01 R':>9}{'S01 t':>8}{'dropped':>9}")

        pooled_cov: list[float] = []
        pooled_s01: list[float] = []
        total_dropped = 0

        for ledger_dir, rel_entry, rel_trend in config["instruments"]:
            ledger = LEDGER_ROOT / ledger_dir / "fixed_trades.csv"
            entry_csv = data_root / rel_entry
            trend_csv = data_root / rel_trend
            if not ledger.exists() or not entry_csv.exists() or not trend_csv.exists():
                print(f"{ledger_dir:<14}  SKIPPED (missing ledger or bars)")
                continue

            rows, _ = label_trades(
                ledger, entry_csv, trend_csv,
                entry_minutes=config["entry_minutes"],
                trend_minutes=config["trend_minutes"],
                use_prior_bar=use_prior_bar,
            )
            # Trades with no confirmation data are excluded from BOTH columns,
            # so the comparison stays like-for-like.
            covered = [r for r, _, _, ok in rows if ok]
            s01 = [r for r, ha_ok, htf_ok, ok in rows if ok and ha_ok and htf_ok]
            dropped = len(rows) - len(covered)
            total_dropped += dropped
            pooled_cov += covered
            pooled_s01 += s01

            n_c, m_c, t_c = mean_and_t(covered)
            n_s, m_s, t_s = mean_and_t(s01)
            print(f"{ledger_dir:<14}{n_c:>7}{m_c:>9.4f}{t_c:>8.2f}"
                  f"{n_s:>8}{m_s:>9.4f}{t_s:>8.2f}{dropped:>9}")

        n_c, m_c, t_c = mean_and_t(pooled_cov)
        n_s, m_s, t_s = mean_and_t(pooled_s01)
        print(f"{'POOLED':<14}{n_c:>7}{m_c:>9.4f}{t_c:>8.2f}"
              f"{n_s:>8}{m_s:>9.4f}{t_s:>8.2f}{total_dropped:>9}")
        if n_c:
            print(f"Strategy 01 gate retains {100 * n_s / n_c:.1f}% of covered trades")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--band", default="both", choices=["15m", "1h", "both"])
    args = parser.parse_args()

    bands = ["15m", "1h"] if args.band == "both" else [args.band]
    for band in bands:
        run_band(band, args.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
