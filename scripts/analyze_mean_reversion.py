"""Does price that has stretched far from a moving average tend to come back?

Measures the market, not a strategy. No entries, no stops, no costs -- just
the relationship between how far a bar closed from its moving average and what
price did next. If that relationship is absent, no amount of rule-craft will
build a mean-reversion strategy on this data, and it is far cheaper to find
out here than after a spec exists.

Pre-stated: extension is ``(close - SMA20) / ATR14`` at each bar, forward
return is ``(close[i+N] - close[i]) / ATR14[i]``, and the primary statistic is
their correlation. **Mean reversion predicts r < 0** -- stretched high, falls
back. Momentum predicts r > 0. The SMA period and the horizons below were
fixed before running; varying them is a sweep for later, not a search now.

Two traps this deliberately avoids:

**Overlapping windows.** Consecutive bars share almost all of their forward
window, so their returns are heavily autocorrelated and a naive t over 34,000
bars would be wildly overstated. Only non-overlapping observations are used --
for horizon N the sample steps N bars at a time, so no two observations share
a bar. This is the single biggest reason a measurement like this produces
false positives.

**Confusing a gradient with an edge.** A real relationship here is necessary
for a mean-reversion strategy, not sufficient. These returns carry no spread,
no commission, no stop, and no path dependence; the collision analysis already
showed how much those matter. Read this as "is there anything here at all".

Causality: SMA and ATR at bar i use only bars up to i; the forward return is
the only thing that looks ahead, which is what it is measuring.

DIA is withheld -- it is the reserved holdout, and reading it here would spend
it on the design rather than the test.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ai_trade.strategy_01 import atr, load_ohlcv_csv  # noqa: E402
from evaluate_holdout_significance import t_sf  # noqa: E402

CACHES: Dict[str, str] = {
    "SPY": "data/market_data/ibkr/SPY/v4_2y/spy_15m.csv",
    "QQQ": "data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv",
    "IWM": "data/market_data/ibkr/IWM/v5_5y/iwm_15m.csv",
    "GLD": "data/market_data/ibkr/GLD/v5_5y/gld_15m.csv",
    "SLV": "data/market_data/ibkr/SLV/v5_5y/slv_15m.csv",
    "EURUSD": "data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv",
    "GBPUSD": "data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv",
    # Reserved holdout; never in the default set.
    "DIA": "data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv",
}
DEFAULT_SYMBOLS = ("SPY", "QQQ", "IWM", "GLD", "SLV", "EURUSD", "GBPUSD")

SMA_PERIOD = 20
ATR_PERIOD = 14
# 1h, 2h, 4h and 8h of 15-minute bars.
HORIZONS: Tuple[int, ...] = (4, 8, 16, 32)

# Extension buckets in ATR units, symmetric and round-numbered.
BUCKETS: Tuple[Tuple[str, float, float], ...] = (
    ("below -3", -math.inf, -3.0),
    ("-3 to -2", -3.0, -2.0),
    ("-2 to -1", -2.0, -1.0),
    ("-1 to 0", -1.0, 0.0),
    ("0 to +1", 0.0, 1.0),
    ("+1 to +2", 1.0, 2.0),
    ("+2 to +3", 2.0, 3.0),
    ("above +3", 3.0, math.inf),
)


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index >= period - 1:
            out[index] = running / period
    return out


def observations(symbol: str, horizon: int) -> List[Tuple[float, float]]:
    """Non-overlapping (extension, forward return) pairs, both in ATR units."""
    bars = load_ohlcv_csv(REPO_ROOT / CACHES[symbol])
    closes = [bar.close for bar in bars]
    averages = sma(closes, SMA_PERIOD)
    volatility = atr(bars, ATR_PERIOD)

    rows: List[Tuple[float, float]] = []
    index = max(SMA_PERIOD, ATR_PERIOD)
    while index + horizon < len(bars):
        average, band = averages[index], volatility[index]
        if average is None or band is None or band <= 0:
            index += 1
            continue
        extension = (closes[index] - average) / float(band)
        forward = (closes[index + horizon] - closes[index]) / float(band)
        rows.append((extension, forward))
        # Step a full horizon so no two observations share a forward window.
        index += horizon
    return rows


def correlation(pairs: Sequence[Tuple[float, float]]) -> Optional[dict]:
    n = len(pairs)
    if n < 3:
        return None
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    r = max(-0.999999, min(0.999999, sxy / math.sqrt(sxx * syy)))
    t = r * math.sqrt(n - 2) / math.sqrt(1 - r * r)
    return {"n": n, "r": r, "t": t, "p": t_sf(t, n - 2)}


def mean_and_t(values: Sequence[float]) -> Optional[dict]:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return {"n": n, "mean": mean, "t": mean / (sd / math.sqrt(n)) if sd > 0 else 0.0}


def positive_control(symbol: str, horizon: int) -> Tuple[Optional[dict], Optional[dict]]:
    """Correlate extension with the PAST return as well as the forward one.

    A null result is only worth believing if the same code can detect a
    relationship that must be there. Extension is built from price and its
    moving average, so it has to track the return that produced it: the past
    correlation should be near +1. If it is not, the null below is a bug
    rather than a finding.
    """
    bars = load_ohlcv_csv(REPO_ROOT / CACHES[symbol])
    closes = [bar.close for bar in bars]
    averages, volatility = sma(closes, SMA_PERIOD), atr(bars, ATR_PERIOD)
    past: List[Tuple[float, float]] = []
    forward: List[Tuple[float, float]] = []
    index = max(SMA_PERIOD, ATR_PERIOD) + horizon
    while index + horizon < len(bars):
        average, band = averages[index], volatility[index]
        if average is not None and band and band > 0:
            extension = (closes[index] - average) / float(band)
            past.append((extension, (closes[index] - closes[index - horizon]) / float(band)))
            forward.append((extension, (closes[index + horizon] - closes[index]) / float(band)))
        index += horizon
    return correlation(past), correlation(forward)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS),
                        choices=sorted(CACHES))
    args = parser.parse_args(argv)

    print("Mean reversion screen -- 15m bars, extension vs forward return, both in ATR units")
    print(f"SMA{SMA_PERIOD}, ATR{ATR_PERIOD}, non-overlapping windows only.")
    print(f"Instruments: {', '.join(args.symbols)}")
    withheld = sorted(set(CACHES) - set(args.symbols))
    if withheld:
        print(f"Withheld (not read): {', '.join(withheld)}")
    print("\nMean reversion predicts r < 0. Momentum predicts r > 0.\n")

    header = f"{'horizon':<10}{'symbol':<9}{'n':>7}{'r':>9}{'t':>8}{'p':>9}"
    print(header)
    print("-" * len(header))

    for horizon in HORIZONS:
        pooled: List[Tuple[float, float]] = []
        for symbol in args.symbols:
            pairs = observations(symbol, horizon)
            pooled += pairs
            c = correlation(pairs)
            if c:
                print(f"{str(horizon) + ' bars':<10}{symbol:<9}{c['n']:>7}"
                      f"{c['r']:>+9.4f}{c['t']:>+8.2f}{c['p']:>9.4f}")
        c = correlation(pooled)
        if c:
            flag = "significant" if c["p"] < 0.05 else ""
            print(f"{'':<10}{'POOLED':<9}{c['n']:>7}{c['r']:>+9.4f}{c['t']:>+8.2f}"
                  f"{c['p']:>9.4f}  {flag}")
        print()

    # Bucket view at the middle horizon, for shape rather than significance.
    shape_horizon = HORIZONS[len(HORIZONS) // 2]
    pooled = [p for s in args.symbols for p in observations(s, shape_horizon)]
    print(f"Pooled forward return by extension bucket, {shape_horizon} bars ahead")
    print(f"{'extension (ATR)':<18}{'n':>8}{'mean fwd R':>13}{'t':>8}")
    print("-" * 47)
    for label, low, high in BUCKETS:
        values = [y for x, y in pooled if low <= x < high]
        s = mean_and_t(values)
        if s:
            print(f"{label:<18}{s['n']:>8}{s['mean']:>+13.4f}{s['t']:>+8.2f}")
    print(f"\nPositive control at {shape_horizon} bars -- extension vs the PAST return,")
    print("which must be strongly positive if the measurement works at all:")
    for symbol in args.symbols:
        past, forward = positive_control(symbol, shape_horizon)
        if past and forward:
            print(f"  {symbol:<8} past r = {past['r']:+.4f} (t = {past['t']:+.1f})"
                  f"   forward r = {forward['r']:+.4f} (t = {forward['t']:+.2f})")

    print("\nA mean-reverting market shows negative forward returns after positive")
    print("extensions and positive ones after negative extensions -- a downward slope")
    print("across this table. No slope means there is nothing here to build on.")
    print("These returns carry no spread, commission, stop or path dependence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
