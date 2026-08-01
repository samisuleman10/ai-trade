"""Parameter sweep for Strategy 04 v1.2 Filter A's max_risk_zone_ratio.

Required by the v1.2 spec before any threshold may be trusted: the 2.5
default was chosen by inspecting the same data it was measured on. Thin
wrapper: the sweep engine lives in ``sweep_version_parameter`` and reads the
registry entry, so the grid and the symbol list cannot drift from the runs.
The one fact this module still owns is that v1.2's sweep isolates Filter A
(variant "a", Filter B off, so any effect is attributable) -- the registry
does not encode which variant a sweep must run. The report is evidence for
a human decision; nothing here selects a threshold.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

from ai_trade.backtest_strategy_01 import BacktestConfig
from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import Strategy04IndicatorParameters
from ai_trade.strategy_registry import VERSIONS
from ai_trade.sweep_version_parameter import run_sweep
from ai_trade.sweep_version_parameter import sweep_symbol as _sweep_symbol

_SPEC = VERSIONS["strategy_04_v1_2"]

# Historical export name for the registry's grid; a drift guard in
# test_strategy_registry pins the two together.
DEFAULT_THRESHOLDS: tuple[float, ...] = _SPEC.sweep_grid

# v1.2 sweeps Filter A alone: enabling Filter B as well would make the
# threshold's effect unattributable.
_SWEEP_VARIANT = "a"


def sweep_symbol(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    indicator_params: Strategy04IndicatorParameters,
    config: BacktestConfig,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> list[dict[str, object]]:
    """Evaluate Filter A alone at each threshold (historical signature)."""
    return _sweep_symbol(
        _SPEC,
        fifteen_minute_bars,
        one_hour_bars,
        indicator_params,
        config,
        thresholds,
        variant=_SWEEP_VARIANT,
    )


def build_parser() -> argparse.ArgumentParser:
    """Symbols come from the registry, so the sweep covers whatever the grid runs."""
    parser = argparse.ArgumentParser(description="Sweep Filter A's max_risk_zone_ratio per symbol.")
    parser.add_argument("--symbols", nargs="+",
                        choices=_SPEC.supported_symbols,
                        default=_SPEC.supported_symbols)
    parser.add_argument("--output", type=Path,
                        default=Path("strategies/strategy_04/v1_2/results/sweep"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    # "risk_ratio_sweep.json" is the historical name the committed sweep and
    # the v1.3 holdout report reference; the generic default would rename it.
    return run_sweep(
        _SPEC,
        args.symbols,
        args.output,
        variant=_SWEEP_VARIANT,
        json_name="risk_ratio_sweep.json",
    )


if __name__ == "__main__":
    raise SystemExit(main())
