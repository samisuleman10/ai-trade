"""How much of a result is the "stop before target" assumption?

``_exit_trade`` resolves a bar that touches both the stop and the target by
taking the stop -- a deliberately conservative choice, since 15-minute bars
hide the path within them. With a 1:1 bracket the two barriers sit close
together, so collisions may be common, and every one of them is recorded as a
full loss that might have been a full win.

That matters because Strategy 03's -0.1033R over 5,602 trades is now the
strongest evidence in this repository. Before it underpins anything further,
its dependence on that single modelling choice has to be known.

This measures, per instrument:

- how many stop exits happened on a bar that also reached the target, and
- an **optimistic bound**: what the average R would be if every one of those
  collisions had gone the other way.

The truth lies between the two, and nearer the pessimistic end for a downward
drift. If the optimistic bound is still significantly negative, the finding
does not rest on the assumption. If it crosses zero, the finding is
assumption-dependent and must say so.

The bound is computed by re-pricing collisions in place, holding the trade set
fixed. A true optimistic re-simulation would also change which bars are free
for the next entry, so the set itself would differ; that is why this is a
bound and a screen, not a second result. ``_fill`` and ``trade_costs`` are
imported rather than restated, so the cost model cannot drift from the engine.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ai_trade.backtest_strategy_01 import BacktestConfig, _fill, trade_costs  # noqa: E402
from ai_trade.fx_config import fx_backtest_config  # noqa: E402
from ai_trade.strategy_01 import load_ohlcv_csv  # noqa: E402
from evaluate_holdout_significance import evaluate  # noqa: E402

# instrument -> (Strategy 03 run directory, the 15m cache it was run on, market)
RUNS: Dict[str, Tuple[str, str, str]] = {
    "SPY": ("spy_15m", "data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "equity"),
    "QQQ": ("qqq_15m", "data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "equity"),
    "DIA": ("us30_dia_15m", "data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "equity"),
    "IWM": ("iwm_15m", "data/market_data/ibkr/IWM/v5_5y/iwm_15m.csv", "equity"),
    "GLD": ("gld_15m", "data/market_data/ibkr/GLD/v5_5y/gld_15m.csv", "equity"),
    "SLV": ("slv_15m", "data/market_data/ibkr/SLV/v5_5y/slv_15m.csv", "equity"),
    "EURUSD": ("eurusd_15m", "data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv", "fx"),
    "GBPUSD": ("gbpusd_15m", "data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv", "fx"),
}

# Strategy 04 v1.2's base variant, same 1:1 bracket and the same engine, so the
# same question applies to the conclusions drawn from it.
RUNS_04: Dict[str, Tuple[str, str, str]] = {
    sym: (f"{sym.lower()}_1h_15m_base", cache, market)
    for sym, cache, market in (
        ("SPY", "data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "equity"),
        ("QQQ", "data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "equity"),
        ("DIA", "data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "equity"),
        ("IWM", "data/market_data/ibkr/IWM/v5_5y/iwm_15m.csv", "equity"),
        ("GLD", "data/market_data/ibkr/GLD/v5_5y/gld_15m.csv", "equity"),
        ("SLV", "data/market_data/ibkr/SLV/v5_5y/slv_15m.csv", "equity"),
        ("EURUSD", "data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv", "fx"),
        ("GBPUSD", "data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv", "fx"),
    )
}

RESULT_ROOTS = {
    "03": ("strategies/strategy_03/v1/results", RUNS),
    "04": ("strategies/strategy_04/v1_2/results", RUNS_04),
}

EQUITY_CONFIG = BacktestConfig(
    allowed_direction="both", block_opening_hour_entries=True,
    block_final_hour_entries=True, block_friday_entries=True,
    entry_interval_minutes=15, force_friday_close=True,
)


def config_for(symbol: str, market: str) -> BacktestConfig:
    return fx_backtest_config(symbol) if market == "fx" else EQUITY_CONFIG


def analyse(symbol: str, strategy: str = "03") -> dict:
    root, runs = RESULT_ROOTS[strategy]
    run_name, cache, market = runs[symbol]
    config = config_for(symbol, market)
    bars = {bar.timestamp: bar for bar in load_ohlcv_csv(REPO_ROOT / cache)}

    path = REPO_ROOT / root / run_name / "fixed_trades.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    actual: List[float] = []
    optimistic: List[float] = []
    collisions = 0
    stops = 0
    missing = 0

    for row in rows:
        result_r = float(row["result_r"])
        actual.append(result_r)
        if row["exit_reason"] != "stop":
            optimistic.append(result_r)
            continue
        stops += 1
        bar = bars.get(row["exit_timestamp"])
        if bar is None:
            missing += 1
            optimistic.append(result_r)
            continue
        side = row["side"]
        target = float(row["target_price"])
        # The engine's own condition, restated in the same direction sense.
        targeted = bar.high >= target if side == "long" else bar.low <= target
        if not targeted:
            optimistic.append(result_r)
            continue
        collisions += 1
        # Re-price this trade as a target fill, using the engine's fill and
        # cost functions so the arithmetic matches a real run.
        entry = float(row["entry_price"])
        quantity = int(row["quantity"])
        exit_price = _fill(target, side, "target", config.slippage_bps_per_side)
        direction = 1 if side == "long" else -1
        gross = quantity * (exit_price - entry) * direction * config.contract_multiplier
        net = gross - trade_costs(entry, exit_price, quantity, config)
        planned_risk = abs(net / result_r) if result_r else 0.0
        # planned_risk is recoverable from the recorded loss; guard the rare
        # zero-R row rather than dividing by it.
        optimistic.append(net / planned_risk if planned_risk else result_r)

    return {
        "symbol": symbol,
        "trades": len(rows),
        "stops": stops,
        "collisions": collisions,
        "missing_bar": missing,
        "actual": evaluate(actual),
        "optimistic": evaluate(optimistic),
        "actual_values": actual,
        "optimistic_values": optimistic,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", nargs="+", default=sorted(RUNS), choices=sorted(RUNS))
    parser.add_argument("--strategy", default="03", choices=sorted(RESULT_ROOTS))
    args = parser.parse_args(argv)

    label = {"03": "Strategy 03 v1", "04": "Strategy 04 v1.2 base"}[args.strategy]
    print(f"{label}, 15m, fixed sizing -- dependence on the intrabar collision rule\n")
    header = (f"{'symbol':<9}{'trades':>7}{'stops':>7}{'collide':>8}{'%all':>7}"
              f"{'%stops':>8}{'actual R':>10}{'optimistic':>11}{'opt t':>8}")
    print(header)
    print("-" * len(header))

    pooled_actual: List[float] = []
    pooled_optimistic: List[float] = []
    for symbol in args.symbols:
        r = analyse(symbol, args.strategy)
        pooled_actual += r["actual_values"]
        pooled_optimistic += r["optimistic_values"]
        pct_all = 100 * r["collisions"] / r["trades"] if r["trades"] else 0
        pct_stops = 100 * r["collisions"] / r["stops"] if r["stops"] else 0
        print(f"{symbol:<9}{r['trades']:>7}{r['stops']:>7}{r['collisions']:>8}"
              f"{pct_all:>6.1f}%{pct_stops:>7.1f}%"
              f"{r['actual']['average_r']:>+10.4f}{r['optimistic']['average_r']:>+11.4f}"
              f"{r['optimistic']['t']:>+8.2f}")
        if r["missing_bar"]:
            print(f"  ({r['missing_bar']} exit bars not found in the cache; left unchanged)")

    a, o = evaluate(pooled_actual), evaluate(pooled_optimistic)
    print("-" * len(header))
    print(f"{'POOLED':<9}{len(pooled_actual):>7}{'':>7}{'':>8}{'':>7}{'':>8}"
          f"{a['average_r']:>+10.4f}{o['average_r']:>+11.4f}{o['t']:>+8.2f}")
    print(f"\nActual (stop-first):     {a['average_r']:+.4f}R, t = {a['t']:+.2f}, "
          f"bar {a['critical']:.3f} -> {a['rule']}")
    print(f"Optimistic (target-first): {o['average_r']:+.4f}R, t = {o['t']:+.2f}, "
          f"bar {o['critical']:.3f} -> {o['rule']}")
    print("\nThe true value lies between these, nearer the pessimistic end.")
    print("If both are significantly negative, the finding does not rest on the assumption.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
