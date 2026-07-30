"""Run one Strategy 04 v1.2 ablation variant on one cached symbol.

The four variants (base / a / b / ab) are parameter configurations of one
signal module, per the v1.2 spec's required ablation. Equity symbols use the
Strategy 04 equity config and default v0.3 indicator; EURUSD/GBPUSD use the
FX session/cost preset and the TPO + fx_17et indicator preset, exactly like
the committed v1.1 FX baselines they are compared against.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from ai_trade.backtest_strategy_01 import (
    BacktestConfig,
    _entry_allowed,
    run_backtest,
    summarize,
    write_results,
)
from ai_trade.backtest_strategy_04_v1 import _config, _write_signals
from ai_trade.fx_config import fx_backtest_config
from ai_trade.publish_run import publish_result_directory
from ai_trade.rrms_five_loss_reset import FIVE_LOSS_TIERS, run_backtest_five_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    strategy_04_v0_3_parameters,
)
from ai_trade.strategy_04_v1_2 import (
    Strategy04V12ExecutionParameters,
    candidate_signals_v1_2,
)
from ai_trade.trade_statistics import ledger_statistics

VARIANTS: dict[str, tuple[bool, bool]] = {
    "base": (False, False),
    "a": (True, False),
    "b": (False, True),
    "ab": (True, True),
}

_EQUITY_DATA = {
    "SPY": ("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
    "QQQ": ("data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "data/market_data/ibkr/QQQ/v5_5y/qqq_1h.csv"),
    "DIA": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "data/market_data/ibkr/US30_DIA/v5_5y/dia_1h.csv"),
}
_FX_DATA = {
    "EURUSD": ("data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv", "data/market_data/ibkr/EURUSD/v1_5y/eurusd_1h.csv"),
    "GBPUSD": ("data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv", "data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_1h.csv"),
}

WARNING = (
    "Historical research only. Version 1.2 is an experiment, not a replacement: "
    "the max_risk_zone_ratio threshold has not been validated (the 2.5 default was "
    "chosen in-sample) and Filter B is a hypothesis from a single reviewed trade. "
    "No configuration is approved for paper or live execution. FX runs additionally "
    "inherit every v1.1 FX caveat (TPO zones, midpoint data, modelled spread, "
    "equity-tuned bar-count parameters)."
)


def symbol_run_inputs(
    symbol: str,
) -> tuple[Path, Path, BacktestConfig, Strategy04IndicatorParameters, str]:
    """Return (fifteen_minute, one_hour, config, indicator_params, market)."""
    symbol = symbol.upper()
    if symbol in _EQUITY_DATA:
        fifteen, hours = _EQUITY_DATA[symbol]
        return Path(fifteen), Path(hours), _config(), strategy_04_v0_3_parameters(), "equity"
    fifteen, hours = _FX_DATA[symbol]
    indicator = replace(
        strategy_04_v0_3_parameters(),
        profile_weighting="time",
        session_day_boundary="fx_17et",
    )
    return Path(fifteen), Path(hours), fx_backtest_config(symbol), indicator, "spot_fx_midpoint"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest one Strategy 04 v1.2 ablation variant.")
    parser.add_argument("--symbol", required=True, choices=("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD"))
    parser.add_argument("--variant", required=True, choices=tuple(VARIANTS))
    parser.add_argument("--max-risk-zone-ratio", type=float, default=2.5)
    parser.add_argument("--fifteen-minute", type=Path, default=None)
    parser.add_argument("--one-hour", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    fifteen_path, hours_path, config, indicator_params, market = symbol_run_inputs(args.symbol)
    if args.fifteen_minute is not None:
        fifteen_path = args.fifteen_minute
    if args.one_hour is not None:
        hours_path = args.one_hour
    output = args.output or Path(
        f"strategies/strategy_04/v1_2/results/{args.symbol.lower()}_1h_15m_{args.variant}"
    )

    enable_a, enable_b = VARIANTS[args.variant]
    execution_params = Strategy04V12ExecutionParameters(
        enable_filter_a=enable_a,
        enable_filter_b=enable_b,
        max_risk_zone_ratio=args.max_risk_zone_ratio,
    )

    fifteen = load_ohlcv_csv(fifteen_path)
    hours = load_ohlcv_csv(hours_path)
    signal_result = candidate_signals_v1_2(fifteen, hours, execution_params, indicator_params)
    signals = signal_result.signals

    output.mkdir(parents=True, exist_ok=True)
    _write_signals(output / "candidate_signals.csv", signals)
    fixed_trades = run_backtest(fifteen, signals, "fixed", config)
    rrms_trades = run_backtest_five_loss_reset(fifteen, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    rrms_summary = summarize(rrms_trades, config.starting_equity)
    write_results(fixed_trades, fixed_summary, "fixed", output)
    write_results(rrms_trades, rrms_summary, "rrms", output)

    fixed_detail = ledger_statistics(output / "fixed_trades.csv")
    rrms_detail = ledger_statistics(output / "rrms_trades.csv")
    eligible = [
        signal for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]
    report = {
        "strategy_id": "strategy_04_v1_2_rejection_filters",
        "mode": "historical_backtest_only",
        "market": market,
        "symbol": args.symbol.upper(),
        "variant": args.variant,
        "data": {
            "fifteen_minute_file": str(fifteen_path),
            "fifteen_minute_bar_count": len(fifteen),
            "fifteen_minute_first": fifteen[0].timestamp,
            "fifteen_minute_last": fifteen[-1].timestamp,
            "one_hour_file": str(hours_path),
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
        "change_from_v1_1": (
            "Filter A rejects reactions whose trigger close sits more than "
            "max_risk_zone_ratio zone-widths from the stop; Filter B rejects "
            "reactions opposing the latest completed one-hour candle. Both are "
            "independently switchable; this run is the "
            f"'{args.variant}' ablation variant."
        ),
        "candidate_signal_count": len(signals),
        "session_eligible_signal_count": len(eligible),
        "results": {
            "fixed": {**fixed_summary, "details": fixed_detail},
            "rrms": {**rrms_summary, "details": rrms_detail},
        },
        "warning": WARNING,
    }
    (output / "backtest_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["results"]["fixed"], indent=2))
    print(f"Saved {args.symbol} v1.2-{args.variant} backtest to {output}")

    if not args.skip_publish:
        bundle_dir = publish_result_directory(output)
        print(f"Published visualization bundle to {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
