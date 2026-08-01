"""Does the Alligator's loss concentrate where the HTF mouth opened long ago?

Tests the mechanism proposed in
``docs/Notes/ideas/htf_alligator_confluence_entry_timing.md`` against trades
that already exist, before any strategy is written. The hypothesis:

    Entries lose because they arrive late in an extended move. If so, the loss
    should be worst where the higher-timeframe Alligator has been open longest,
    and shrink toward zero -- or turn positive -- where it has just opened.

This measures Strategy 03 v1's recorded 15-minute trades. It adds no rule and
selects no threshold; the point is to find out whether the gradient exists at
all, because if it does not, the strategy built on it cannot work for the
reason claimed.

**Primary statistic is the correlation between HTF age and trade R, not the
best bucket.** Scanning five buckets across two higher timeframes and
reporting the most favourable one is how a gradient gets manufactured from
noise. The correlation is a single pre-stated test of a single directional
prediction; the bucket table below it is for diagnosis only.

Unlike the audit modules, this deliberately imports ``alligator_points``: the
whole question is what the *same* Alligator definition was doing on a higher
timeframe, so re-deriving it independently would test a different indicator.

Causality: an HTF bar stamped T covering M minutes is only complete at T+M, so
a trade deciding at D may use it only when T+M <= D. Nothing here may see a
bar that had not finished when the trade was taken.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ai_trade.strategy_01 import alligator_points, load_ohlcv_csv  # noqa: E402
from evaluate_holdout_significance import t_critical_95, t_sf  # noqa: E402

# Instrument -> (Strategy 03 run directory, 15m cache, {htf label: (cache, minutes)}).
# The caches are the ones each committed run actually read, checked against the
# date range recorded in its backtest_report.json; a different cache would be a
# different experiment.
INSTRUMENTS: Dict[str, dict] = {
    "SPY": {
        "run": "strategies/strategy_03/v1/results/spy_15m",
        "htf": {
            "1h": ("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv", 60),
            "4h": ("data/market_data/ibkr/SPY/v4_2y/spy_4h.csv", 240),
        },
    },
    "QQQ": {
        "run": "strategies/strategy_03/v1/results/qqq_15m",
        "htf": {
            "1h": ("data/market_data/ibkr/QQQ/v5_5y/qqq_1h.csv", 60),
            "4h": ("data/market_data/ibkr/QQQ/v5_5y/qqq_4h.csv", 240),
        },
    },
    # DIA is deliberately absent: it is reserved as a holdout for whatever this
    # analysis motivates. Adding it here spends that reserve.
    "DIA": {
        "run": "strategies/strategy_03/v1/results/us30_dia_15m",
        "htf": {
            "1h": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_1h.csv", 60),
            "4h": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_4h.csv", 240),
        },
    },
}

DEFAULT_SYMBOLS = ("SPY", "QQQ")

# Reported in HTF bars since the mouth opened. Edges are round numbers chosen
# before seeing any result, not tuned to the data.
AGE_BUCKETS: Tuple[Tuple[str, int, float], ...] = (
    ("1 (just opened)", 1, 1),
    ("2-3", 2, 3),
    ("4-6", 4, 6),
    ("7-12", 7, 12),
    ("13+", 13, math.inf),
)


def _parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def htf_state_series(cache: Path, minutes: int) -> List[Tuple[datetime, str, int]]:
    """(bar completion time, state, bars in that state) for each HTF bar.

    ``state`` is "bull", "bear" or "none". The age counts consecutive bars in
    the current state, so a mouth that opened on this very bar has age 1.
    """
    bars = load_ohlcv_csv(cache)
    points = alligator_points(bars)
    series: List[Tuple[datetime, str, int]] = []
    previous_state, age = None, 0
    for bar, point in zip(bars, points):
        if point.bullish_open:
            state = "bull"
        elif point.bearish_open:
            state = "bear"
        else:
            state = "none"
        age = 1 if state != previous_state else age + 1
        previous_state = state
        series.append((_parse(bar.timestamp) + timedelta(minutes=minutes), state, age))
    return series


def state_at(series: Sequence[Tuple[datetime, str, int]], decision: datetime) -> Optional[Tuple[str, int]]:
    """The newest HTF bar that had already completed when the trade decided."""
    low, high, found = 0, len(series) - 1, None
    while low <= high:
        mid = (low + high) // 2
        if series[mid][0] <= decision:
            found = mid
            low = mid + 1
        else:
            high = mid - 1
    if found is None:
        return None
    return series[found][1], series[found][2]


def load_trades(run_dir: Path) -> List[Tuple[datetime, str, float]]:
    with (run_dir / "fixed_trades.csv").open(newline="", encoding="utf-8") as handle:
        return [
            (_parse(row["decision_timestamp"]), row["side"], float(row["result_r"]))
            for row in csv.DictReader(handle)
        ]


def summarize(values: Sequence[float]) -> Optional[dict]:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    t = mean / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"n": n, "mean": mean, "sd": sd, "t": t, "critical": t_critical_95(n - 1)}


def correlation(xs: Sequence[float], ys: Sequence[float]) -> Optional[dict]:
    """Pearson r between HTF age and trade R, with its two-sided p.

    This is the pre-stated test. The hypothesis predicts r < 0: older mouth,
    worse outcome.
    """
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    r = max(-0.999999, min(0.999999, r))
    t = r * math.sqrt(n - 2) / math.sqrt(1 - r * r)
    return {"n": n, "r": r, "t": t, "p": t_sf(t, n - 2)}


def analyse(symbols: Sequence[str], htf_label: str) -> dict:
    agreeing: List[Tuple[float, float]] = []   # (age, R) where HTF agrees with the trade
    buckets: Dict[str, List[float]] = {label: [] for label, _, _ in AGE_BUCKETS}
    opposing: List[float] = []
    closed: List[float] = []
    per_symbol: Dict[str, List[Tuple[float, float]]] = {}
    unusable = 0

    for symbol in symbols:
        spec = INSTRUMENTS[symbol]
        cache, minutes = spec["htf"][htf_label]
        series = htf_state_series(REPO_ROOT / cache, minutes)
        rows = []
        for decision, side, result_r in load_trades(REPO_ROOT / spec["run"]):
            state = state_at(series, decision)
            if state is None:
                # No completed HTF bar yet -- the trade predates the indicator's
                # warm-up. Counted and excluded, never silently dropped.
                unusable += 1
                continue
            htf_state, age = state
            wanted = "bull" if side == "long" else "bear"
            if htf_state == "none":
                closed.append(result_r)
            elif htf_state != wanted:
                opposing.append(result_r)
            else:
                agreeing.append((float(age), result_r))
                rows.append((float(age), result_r))
                for label, low, high in AGE_BUCKETS:
                    if low <= age <= high:
                        buckets[label].append(result_r)
                        break
        per_symbol[symbol] = rows

    ages = [a for a, _ in agreeing]
    returns = [r for _, r in agreeing]
    return {
        "htf": htf_label,
        "correlation": correlation(ages, returns),
        "buckets": {label: summarize(v) for label, v in buckets.items()},
        "agreeing": summarize(returns),
        "opposing": summarize(opposing),
        "closed": summarize(closed),
        "per_symbol": {s: correlation([a for a, _ in v], [r for _, r in v]) for s, v in per_symbol.items()},
        "unusable": unusable,
    }


def _line(label: str, s: Optional[dict]) -> str:
    if s is None:
        return f"  {label:<22} (too few trades)"
    verdict = "significant" if abs(s["t"]) >= s["critical"] else ""
    return (f"  {label:<22}{s['n']:>6}{s['mean']:>+10.4f}{s['t']:>+8.2f}"
            f"{s['critical']:>8.3f}  {verdict}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS),
                        choices=sorted(INSTRUMENTS))
    parser.add_argument("--htf", nargs="+", default=["1h", "4h"], choices=["1h", "4h"])
    args = parser.parse_args(argv)

    print(f"Strategy 03 v1 15m trades, bucketed by higher-timeframe Alligator age")
    print(f"Instruments analysed: {', '.join(args.symbols)}")
    withheld = sorted(set(INSTRUMENTS) - set(args.symbols))
    if withheld:
        print(f"Withheld as holdout (not read): {', '.join(withheld)}")

    for htf_label in args.htf:
        result = analyse(args.symbols, htf_label)
        print(f"\n{'=' * 74}\nHTF = {htf_label}")
        corr = result["correlation"]
        if corr:
            direction = "supports" if corr["r"] < 0 else "contradicts"
            print(f"\nPRE-STATED TEST -- correlation(HTF age, trade R) over {corr['n']} agreeing trades")
            print(f"  r = {corr['r']:+.4f}   t = {corr['t']:+.2f}   p = {corr['p']:.4f}"
                  f"   -> {direction} the hypothesis"
                  f"{' (significant)' if corr['p'] < 0.05 else ' (not significant)'}")
            for symbol, per in result["per_symbol"].items():
                if per:
                    print(f"    {symbol}: r = {per['r']:+.4f}, t = {per['t']:+.2f}, "
                          f"p = {per['p']:.4f}, n = {per['n']}")

        print(f"\nDIAGNOSTIC buckets (not a selection){'':<3}{'n':>5}{'avg R':>10}{'t':>8}{'bar':>8}")
        for label, _, _ in AGE_BUCKETS:
            print(_line(label, result["buckets"][label]))
        print("  " + "-" * 60)
        print(_line("all agreeing", result["agreeing"]))
        print(_line("HTF opposing", result["opposing"]))
        print(_line("HTF mouth closed", result["closed"]))
        if result["unusable"]:
            print(f"  ({result['unusable']} trades had no completed HTF bar yet; excluded)")

    print("\nNo threshold is selected by this report. A real mechanism should show a")
    print("monotonic gradient, not a single favourable bucket.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
