"""Run one Strategy 04 v1.2 ablation variant on one cached symbol.

Thin wrapper: everything version-specific now lives in the registry entry
(``strategy_registry.VERSIONS["strategy_04_v1_2"]``) and the plumbing in
``run_strategy_version``. This module keeps the historical CLI and the
exports the sweep, ablation summary, grid and reproduction script import,
each re-derived from the registry so the two cannot drift apart.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_trade.backtest_strategy_01 import BacktestConfig
from ai_trade.run_strategy_version import run_version
from ai_trade.run_strategy_version import symbol_run_inputs as _symbol_run_inputs
from ai_trade.strategy_04_indicator import Strategy04IndicatorParameters
from ai_trade.strategy_registry import VERSIONS

_SPEC = VERSIONS["strategy_04_v1_2"]

_EQUITY_DATA = dict(_SPEC.equity_data)
_FX_DATA = dict(_SPEC.fx_data)

# Every symbol this version can run, derived from the caches so the list
# cannot drift from the data. The sweep, the ablation summary and the ablation
# grid all read this: three hand-maintained copies is how IWM, GLD and SLV came
# to be backtested but silently absent from the summary table.
SUPPORTED_SYMBOLS: tuple[str, ...] = _SPEC.supported_symbols

WARNING = _SPEC.warning


def _filter_flags(overrides: dict) -> tuple[bool, bool]:
    """Instantiate the registry overrides so the tuple reflects what runs."""
    params = _SPEC.params_type(**overrides)
    return params.enable_filter_a, params.enable_filter_b


# Historical export shape: variant -> (enable_filter_a, enable_filter_b).
VARIANTS: dict[str, tuple[bool, bool]] = {
    name: _filter_flags(dict(overrides)) for name, overrides in _SPEC.variants.items()
}


def symbol_run_inputs(
    symbol: str,
) -> tuple[Path, Path, BacktestConfig, Strategy04IndicatorParameters, str]:
    """Return (fifteen_minute, one_hour, config, indicator_params, market)."""
    return _symbol_run_inputs(_SPEC, symbol)


def main() -> int:
    # The parser stays here, not in the generic runner, so this CLI's surface
    # (flags, choices, error text) is exactly what it was before the registry.
    parser = argparse.ArgumentParser(description="Backtest one Strategy 04 v1.2 ablation variant.")
    parser.add_argument(
        "--symbol",
        required=True,
        choices=SUPPORTED_SYMBOLS,
    )
    parser.add_argument("--variant", required=True, choices=tuple(VARIANTS))
    parser.add_argument("--max-risk-zone-ratio", type=float, default=_SPEC.sweep_default)
    parser.add_argument("--fifteen-minute", type=Path, default=None)
    parser.add_argument("--one-hour", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    return run_version(
        _SPEC,
        args.symbol,
        args.variant,
        sweep_value=args.max_risk_zone_ratio,
        fifteen_minute=args.fifteen_minute,
        one_hour=args.one_hour,
        output=args.output,
        skip_publish=args.skip_publish,
    )


if __name__ == "__main__":
    raise SystemExit(main())
