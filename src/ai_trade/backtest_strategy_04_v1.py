"""Historical SPY backtest for Strategy 04 v1.

This command consumes local cached bars, builds causal one-hour zones, creates
15-minute reaction signals, and compares fixed sizing with capped five-loss
RRMS. It cannot submit broker orders.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from ai_trade.backtest_strategy_01 import (
    BacktestConfig,
    _entry_allowed,
    run_backtest,
    summarize,
    write_results,
)
from ai_trade.rrms_five_loss_reset import FIVE_LOSS_TIERS, run_backtest_five_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters
from ai_trade.strategy_04_v1 import Strategy04ExecutionParameters, candidate_signals_v1
from ai_trade.trade_statistics import ledger_statistics


def _write_signals(path: Path, signals: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not signals:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(signals[0]))
        writer.writeheader()
        writer.writerows(signals)


def _config() -> BacktestConfig:
    return BacktestConfig(
        starting_equity=100_000.0,
        fixed_risk_percent=0.0015,
        slippage_bps_per_side=1.0,
        commission_per_share_per_side=0.005,
        allowed_direction="both",
        block_opening_hour_entries=True,
        block_final_hour_entries=True,
        block_friday_entries=True,
        entry_interval_minutes=15,
        force_friday_close=True,
        session_timezone="America/New_York",
        friday_close_time=(16, 0),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backtest Strategy 04 v1 one-hour zones with 15-minute reactions."
    )
    parser.add_argument(
        "--fifteen-minute",
        type=Path,
        default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"),
    )
    parser.add_argument(
        "--one-hour",
        type=Path,
        default=Path("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("strategies/strategy_04/v1/results/spy_1h_15m"),
    )
    args = parser.parse_args()

    fifteen = load_ohlcv_csv(args.fifteen_minute)
    hours = load_ohlcv_csv(args.one_hour)
    execution_params = Strategy04ExecutionParameters()
    indicator_params = strategy_04_v0_3_parameters()
    signal_result = candidate_signals_v1(
        fifteen,
        hours,
        execution_params,
        indicator_params,
    )
    signals = signal_result.signals
    config = _config()

    args.output.mkdir(parents=True, exist_ok=True)
    signals_path = args.output / "candidate_signals.csv"
    _write_signals(signals_path, signals)

    fixed_trades = run_backtest(fifteen, signals, "fixed", config)
    rrms_trades = run_backtest_five_loss_reset(fifteen, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    rrms_summary = summarize(rrms_trades, config.starting_equity)
    write_results(fixed_trades, fixed_summary, "fixed", args.output)
    write_results(rrms_trades, rrms_summary, "rrms", args.output)

    fixed_detail = ledger_statistics(args.output / "fixed_trades.csv")
    rrms_detail = ledger_statistics(args.output / "rrms_trades.csv")
    eligible = [
        signal
        for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]

    report = {
        "strategy_id": "strategy_04_v1_1h_zones_15m_reaction",
        "mode": "historical_backtest_only",
        "symbol": "SPY",
        "data": {
            "fifteen_minute_file": str(args.fifteen_minute),
            "fifteen_minute_bar_count": len(fifteen),
            "fifteen_minute_first": fifteen[0].timestamp,
            "fifteen_minute_last": fifteen[-1].timestamp,
            "one_hour_file": str(args.one_hour),
            "one_hour_bar_count": len(hours),
            "one_hour_first": hours[0].timestamp,
            "one_hour_last": hours[-1].timestamp,
        },
        "indicator_version": "0.3",
        "indicator_parameters": asdict(indicator_params),
        "indicator_summary": signal_result.indicator.summary,
        "execution_parameters": asdict(execution_params),
        "backtest_configuration": {
            **asdict(config),
            "rrms_tiers": list(FIVE_LOSS_TIERS),
            "rrms_reset": "after profit or after the fifth consecutive negative exit",
        },
        "rules": {
            "zone_availability": "qualified before the 15-minute trigger bar opens",
            "long_trigger": "valid-side approach, demand-zone intersection, bullish close above zone",
            "short_trigger": "valid-side approach, supply-zone intersection, bearish close below zone",
            "entry": "next immediately following 15-minute bar open",
            "stop": "outside one-hour zone by 0.05 x latest completed one-hour ATR(14)",
            "target": "1.0R",
            "overlap": "stop assumed before target",
            "zone_reuse": "one signal per zone; overlapping zones consumed together",
            "opening_hour": "blocked before 10:30 America/New_York",
            "final_hour": "blocked from 15:00 America/New_York",
            "friday_entries": "blocked",
            "weekend": "force close final Friday 15-minute bar ending at 16:00 America/New_York",
        },
        "candidate_signal_count": len(signals),
        "session_eligible_signal_count": len(eligible),
        "results": {
            "fixed": {**fixed_summary, "details": fixed_detail},
            "rrms": {**rrms_summary, "details": rrms_detail},
        },
        "warning": (
            "Historical research only. No macro regime filter, live order permission, "
            "market-impact model, or out-of-sample validation is included."
        ),
    }
    (args.output / "backtest_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["results"], indent=2))
    print(f"Saved Strategy 04 v1 backtest to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

