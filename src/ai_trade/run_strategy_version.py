"""Run one registered strategy version's ablation variant on one cached symbol.

The plumbing here is version-agnostic on purpose: resolve the symbol's caches,
build execution parameters for a variant, run the backtest, write the evidence
files, assemble ``backtest_report.json``. Everything that actually differs
between versions comes from the ``VersionSpec`` in ``strategy_registry``, so a
new version is a registry entry plus its rules module, not another copy of
this file.

Equity symbols use the Strategy 04 equity config and default v0.3 indicator;
FX symbols use the FX session/cost preset and the TPO + fx_17et indicator
preset, exactly like the committed v1.1 FX baselines they are compared
against.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Optional, Tuple

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
from ai_trade.strategy_registry import VERSIONS, VersionSpec
from ai_trade.trade_statistics import ledger_statistics


def symbol_run_inputs(
    spec: VersionSpec, symbol: str
) -> Tuple[Path, Path, BacktestConfig, Strategy04IndicatorParameters, str]:
    """Return (fifteen_minute, one_hour, config, indicator_params, market)."""
    symbol = symbol.upper()
    if symbol in spec.equity_data:
        fifteen, hours = spec.equity_data[symbol]
        return Path(fifteen), Path(hours), _config(), strategy_04_v0_3_parameters(), "equity"
    fifteen, hours = spec.fx_data[symbol]
    indicator = replace(
        strategy_04_v0_3_parameters(),
        profile_weighting="time",
        session_day_boundary="fx_17et",
    )
    return Path(fifteen), Path(hours), fx_backtest_config(symbol), indicator, "spot_fx_midpoint"


def run_version(
    spec: VersionSpec,
    symbol: str,
    variant: str,
    *,
    sweep_value: Optional[float] = None,
    fifteen_minute: Optional[Path] = None,
    one_hour: Optional[Path] = None,
    output: Optional[Path] = None,
    skip_publish: bool = False,
) -> int:
    """Execute one symbol/variant run and write the evidence contract files."""
    fifteen_path, hours_path, config, indicator_params, market = symbol_run_inputs(spec, symbol)
    if fifteen_minute is not None:
        fifteen_path = fifteen_minute
    if one_hour is not None:
        hours_path = one_hour
    if output is None:
        output = Path(spec.results_template.format(symbol=symbol.lower(), variant=variant))

    # Variant overrides on top of the parameter dataclass's defaults; the
    # sweep parameter rides alongside so the sweep CLI needs no special case.
    overrides = dict(spec.variants[variant])
    if sweep_value is not None:
        overrides[spec.sweep_parameter] = sweep_value
    execution_params = spec.params_type(**overrides)

    fifteen = load_ohlcv_csv(fifteen_path)
    hours = load_ohlcv_csv(hours_path)
    signal_result = spec.signal_builder(fifteen, hours, execution_params, indicator_params)
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
        "strategy_id": spec.report_strategy_id,
        "mode": "historical_backtest_only",
        "market": market,
        "symbol": symbol.upper(),
        "variant": variant,
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
        "indicator_version": spec.indicator_version,
        "indicator_parameters": asdict(indicator_params),
        "indicator_summary": signal_result.indicator.summary,
        "execution_parameters": asdict(execution_params),
        "backtest_configuration": {
            **asdict(config),
            "rrms_tiers": list(FIVE_LOSS_TIERS),
            "rrms_reset": "after profit or after the fifth consecutive negative exit",
        },
        # Keyed change_from_<incumbent>: visualization_contract discovers the
        # run's provenance by scanning for exactly one such key, so the name
        # must come from the registry, in this exact position in the report.
        spec.change_key: spec.change_description.format(variant=variant),
        "candidate_signal_count": len(signals),
        "session_eligible_signal_count": len(eligible),
        "results": {
            "fixed": {**fixed_summary, "details": fixed_detail},
            "rrms": {**rrms_summary, "details": rrms_detail},
        },
        "warning": spec.warning,
    }
    (output / "backtest_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["results"]["fixed"], indent=2))
    print(f"Saved {symbol} {spec.version_label}-{variant} backtest to {output}")

    if not skip_publish:
        bundle_dir = publish_result_directory(output)
        print(f"Published visualization bundle to {bundle_dir}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    # Two-stage parse: --version decides the symbol/variant choices and the
    # sweep flag's name, so it must be known before the real parser is built.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--version")
    known, _ = pre.parse_known_args(argv)
    spec = VERSIONS.get(known.version) if known.version else None

    parser = argparse.ArgumentParser(
        description="Backtest one ablation variant of a registered strategy version."
    )
    parser.add_argument("--version", required=True, choices=tuple(VERSIONS))
    if spec is not None:
        parser.add_argument("--symbol", required=True, choices=spec.supported_symbols)
        parser.add_argument("--variant", required=True, choices=tuple(spec.variants))
        parser.add_argument(
            "--" + spec.sweep_parameter.replace("_", "-"),
            dest="sweep_value",
            type=float,
            default=spec.sweep_default,
        )
        parser.add_argument("--fifteen-minute", type=Path, default=None)
        parser.add_argument("--one-hour", type=Path, default=None)
        parser.add_argument("--output", type=Path, default=None)
        parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args(argv)

    return run_version(
        VERSIONS[args.version],
        args.symbol,
        args.variant,
        sweep_value=args.sweep_value,
        fifteen_minute=args.fifteen_minute,
        one_hour=args.one_hour,
        output=args.output,
        skip_publish=args.skip_publish,
    )


if __name__ == "__main__":
    raise SystemExit(main())
