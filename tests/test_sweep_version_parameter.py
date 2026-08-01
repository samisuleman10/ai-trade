"""The generic sweep must reproduce the pre-refactor v1.2 sweep exactly.

The committed SWEEP.md is deliberately not regenerated (it predates three
instruments), so equivalence is proven here instead: the loop below is the
v1.2 sweep exactly as it was written before Task A3, and both the generic
module and the historical wrapper must return the same rows on real SPY
data.
"""

from pathlib import Path

import pytest

from ai_trade.backtest_strategy_01 import run_backtest, summarize
from ai_trade.run_strategy_version import symbol_run_inputs
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import build_one_hour_indicator
from ai_trade.strategy_04_v1_2 import (
    Strategy04V12ExecutionParameters,
    signals_from_zone_events_v1_2,
)
from ai_trade.strategy_registry import VERSIONS
from ai_trade.summarize_version_ablation import baseline_variant
from ai_trade.sweep_strategy_04_v1_2_risk_ratio import sweep_symbol as wrapper_sweep_symbol
from ai_trade.sweep_version_parameter import build_parser, sweep_symbol

SPEC = VERSIONS["strategy_04_v1_2"]
THRESHOLDS = (1.5, 2.5, 4.0)
_SPY_FIFTEEN = Path(SPEC.equity_data["SPY"][0])


def test_default_symbols_are_every_symbol_the_registry_supports():
    """The threshold evidence must cover the same symbols the grid runs."""
    parsed = build_parser(SPEC).parse_args(["--version", SPEC.version_id, "--variant", "a"])
    assert tuple(parsed.symbols) == SPEC.supported_symbols
    assert len(parsed.symbols) == 8


def test_variant_is_required_because_the_registry_does_not_encode_it():
    """Guessing which variant isolates the parameter would be silently wrong."""
    with pytest.raises(SystemExit):
        build_parser(SPEC).parse_args(["--version", SPEC.version_id])


def test_baseline_variant_is_the_empty_override():
    assert baseline_variant(SPEC) == "base"


def _pre_refactor_rows(fifteen, hours, indicator_params, config, thresholds):
    """The v1.2 sweep loop verbatim as it existed before Task A3."""
    indicator = build_one_hour_indicator(hours, indicator_params)
    unfiltered = signals_from_zone_events_v1_2(
        fifteen, hours, indicator.events, Strategy04V12ExecutionParameters()
    )
    rows = []
    for threshold in thresholds:
        params = Strategy04V12ExecutionParameters(
            enable_filter_a=True, max_risk_zone_ratio=threshold
        )
        signals = signals_from_zone_events_v1_2(fifteen, hours, indicator.events, params)
        trades = run_backtest(fifteen, signals, "fixed", config)
        summary = summarize(trades, config.starting_equity)
        rows.append(
            {
                "threshold": threshold,
                "candidate_signal_count": len(signals),
                "rejected_vs_unfiltered": len(unfiltered) - len(signals),
                "trade_count": summary["trade_count"],
                "win_rate": summary["win_rate"],
                "average_r": summary["average_r"],
                "net_pnl": summary["net_pnl"],
            }
        )
    return rows


@pytest.mark.skipif(
    not _SPY_FIFTEEN.exists(),
    reason="SPY cache absent (data/ is gitignored; run from the main checkout)",
)
def test_generic_and_wrapper_match_the_pre_refactor_sweep_on_spy():
    fifteen_path, hours_path, config, indicator_params, _ = symbol_run_inputs(SPEC, "SPY")
    fifteen = load_ohlcv_csv(fifteen_path)
    hours = load_ohlcv_csv(hours_path)

    expected = _pre_refactor_rows(fifteen, hours, indicator_params, config, THRESHOLDS)
    generic = sweep_symbol(
        SPEC, fifteen, hours, indicator_params, config, THRESHOLDS, variant="a"
    )
    wrapper = wrapper_sweep_symbol(fifteen, hours, indicator_params, config, THRESHOLDS)

    assert generic == expected
    assert wrapper == generic
