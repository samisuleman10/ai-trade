"""Run Strategy 04 v1.1 on cached spot-FX midpoint data (EURUSD, GBPUSD)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from ai_trade.backtest_strategy_01 import _entry_allowed, run_backtest, summarize, write_results
from ai_trade.backtest_strategy_04_v1 import _write_signals
from ai_trade.fx_config import fx_backtest_config
from ai_trade.publish_run import publish_result_directory
from ai_trade.rrms_five_loss_reset import FIVE_LOSS_TIERS, run_backtest_five_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters
from ai_trade.strategy_04_v1_1 import (
    Strategy04V11ExecutionParameters,
    candidate_signals_v1_1,
)
from ai_trade.trade_statistics import ledger_statistics

WARNING = (
    "Historical research only. Spot-FX midpoint data: zones are TPO-qualified "
    "(time-at-price, no volume exists), fills assume a fixed modelled half-spread, "
    "and commission is IBKR IDEALPRO tier-1 bps of notional. Read the TPO-vs-volume "
    "bridge report (strategies/strategy_04/analysis/tpo_vs_volume) before comparing "
    "against any equity result. The indicator's bar-count parameters "
    "(volume_reference_max_age_bars, max_zone_age_bars, broken_retest_window_bars, "
    "etc.) were tuned on ~7-bars/session equity RTH data; FX sessions run ~24 "
    "bars/session, so those windows are roughly 3.4x tighter in wall-clock terms "
    "here and have not been re-tuned for FX bar scale."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Strategy 04 v1.1 on cached spot-FX data.")
    parser.add_argument("--pair", required=True, choices=("EURUSD", "GBPUSD"))
    parser.add_argument("--fifteen-minute", required=True, type=Path)
    parser.add_argument("--one-hour", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    fifteen = load_ohlcv_csv(args.fifteen_minute)
    hours = load_ohlcv_csv(args.one_hour)
    execution_params = Strategy04V11ExecutionParameters()
    indicator_params = replace(
        strategy_04_v0_3_parameters(),
        profile_weighting="time",
        session_day_boundary="fx_17et",
    )
    signal_result = candidate_signals_v1_1(fifteen, hours, execution_params, indicator_params)
    signals = signal_result.signals
    config = fx_backtest_config(args.pair)

    args.output.mkdir(parents=True, exist_ok=True)
    _write_signals(args.output / "candidate_signals.csv", signals)
    fixed_trades = run_backtest(fifteen, signals, "fixed", config)
    rrms_trades = run_backtest_five_loss_reset(fifteen, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    rrms_summary = summarize(rrms_trades, config.starting_equity)
    write_results(fixed_trades, fixed_summary, "fixed", args.output)
    write_results(rrms_trades, rrms_summary, "rrms", args.output)

    fixed_detail = ledger_statistics(args.output / "fixed_trades.csv")
    rrms_detail = ledger_statistics(args.output / "rrms_trades.csv")
    eligible = [
        signal for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]
    report = {
        "strategy_id": "strategy_04_v1_1_shallow_long_penetration",
        "mode": "historical_backtest_only",
        "market": "spot_fx_midpoint",
        "symbol": args.pair.upper(),
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
        "change_from_v1": (
            "Long trigger low may penetrate no more than 25% of demand-zone width. "
            "Shorts and every other rule are unchanged."
        ),
        "candidate_signal_count": len(signals),
        "session_eligible_signal_count": len(eligible),
        "results": {
            "fixed": {**fixed_summary, "details": fixed_detail},
            "rrms": {**rrms_summary, "details": rrms_detail},
        },
        "warning": WARNING,
    }
    (args.output / "backtest_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["results"], indent=2))
    print(f"Saved {args.pair} Strategy 04 v1.1 FX backtest to {args.output}")

    if not args.skip_publish:
        bundle_dir = publish_result_directory(args.output)
        print(f"Published visualization bundle to {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
