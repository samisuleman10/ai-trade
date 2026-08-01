"""Registry of runnable strategy versions.

Everything the pipeline needs that differs between versions lives in one
``VersionSpec``: the signal builder, the variant grid, the data caches, the
sweep definition and the report prose. The runner, sweep, ablation summary
and grid read the spec instead of each growing another version-named copy —
three hand-maintained symbol lists is how IWM, GLD and SLV came to be
backtested but silently absent from the summary table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Tuple

from ai_trade.strategy_04_v1_2 import (
    Strategy04V12ExecutionParameters,
    candidate_signals_v1_2,
)


@dataclass(frozen=True)
class VersionSpec:
    """One strategy version, as the generic pipeline sees it.

    Fields are declarative values, not behaviour: the only callables are the
    signal builder and the parameter dataclass, both defined in the version's
    own rules module. The audit deliberately reads none of this — it re-derives
    filter decisions from recorded CSV columns (see ``verify_strategy_04_v1_2``).
    """

    version_id: str
    strategy_id: str
    # Human-facing label used in run output ("Saved SPY v1.2-ab ...").
    version_label: str
    # The version this one is measured against. The report key encoding it
    # (``change_from_<incumbent>``) is derived, never hardcoded — see change_key.
    incumbent: str
    # The strategy_id string recorded in backtest_report.json; it carries a
    # descriptive suffix ("_rejection_filters") the bare version id does not.
    report_strategy_id: str
    signal_builder: Callable[..., Any]
    params_type: type
    indicator_version: str
    # Variant name -> parameter overrides applied on top of params_type's
    # defaults. The ablation base is the empty override.
    variants: Mapping[str, Mapping[str, object]]
    # Symbol -> (fifteen-minute cache, one-hour cache). Two tables because the
    # runner dispatches equity vs FX configs on membership.
    equity_data: Mapping[str, Tuple[str, str]]
    fx_data: Mapping[str, Tuple[str, str]]
    # Where a run lands by default; placeholders: {symbol} (lowercase), {variant}.
    results_template: str
    # Columns the rules module appends beyond the shared signal schema. The
    # independent audit re-derives filter decisions from these, and the parity
    # diff strips them before comparing against the incumbent.
    audit_columns: Tuple[str, ...]
    # The one tunable the spec requires sweeping before its threshold may be
    # trusted, and the grid of values to sweep it over.
    sweep_parameter: str
    sweep_grid: Tuple[float, ...]
    # Prose recorded under change_key; may reference {variant}.
    change_description: str
    warning: str

    @property
    def supported_symbols(self) -> Tuple[str, ...]:
        """Derived from the caches so the list cannot drift from the data."""
        return tuple(self.equity_data) + tuple(self.fx_data)

    @property
    def change_key(self) -> str:
        """The report key naming the incumbent (``change_from_v1_1``).

        ``visualization_contract._published_condition`` discovers a run's
        provenance by scanning for keys starting with ``change_from_`` and
        goes silently ``None`` unless exactly one exists, so the runner must
        build the key from here rather than hardcode it per version.
        """
        return f"change_from_{self.incumbent}"

    @property
    def sweep_default(self) -> float:
        """The parameter dataclass's own default, so CLI and spec cannot disagree."""
        return getattr(self.params_type(), self.sweep_parameter)


VERSIONS: Dict[str, VersionSpec] = {
    "strategy_04_v1_2": VersionSpec(
        version_id="strategy_04_v1_2",
        strategy_id="strategy_04",
        version_label="v1.2",
        incumbent="v1_1",
        report_strategy_id="strategy_04_v1_2_rejection_filters",
        signal_builder=candidate_signals_v1_2,
        params_type=Strategy04V12ExecutionParameters,
        indicator_version="0.3",
        # The four variants required by the v1.2 spec's ablation: each filter
        # independently switchable so any effect is attributable.
        variants={
            "base": {},
            "a": {"enable_filter_a": True},
            "b": {"enable_filter_b": True},
            "ab": {"enable_filter_a": True, "enable_filter_b": True},
        },
        equity_data={
            "SPY": ("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
            "QQQ": ("data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "data/market_data/ibkr/QQQ/v5_5y/qqq_1h.csv"),
            "DIA": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "data/market_data/ibkr/US30_DIA/v5_5y/dia_1h.csv"),
            "IWM": ("data/market_data/ibkr/IWM/v5_5y/iwm_15m.csv", "data/market_data/ibkr/IWM/v5_5y/iwm_1h.csv"),
            "GLD": ("data/market_data/ibkr/GLD/v5_5y/gld_15m.csv", "data/market_data/ibkr/GLD/v5_5y/gld_1h.csv"),
            "SLV": ("data/market_data/ibkr/SLV/v5_5y/slv_15m.csv", "data/market_data/ibkr/SLV/v5_5y/slv_1h.csv"),
        },
        fx_data={
            "EURUSD": ("data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv", "data/market_data/ibkr/EURUSD/v1_5y/eurusd_1h.csv"),
            "GBPUSD": ("data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv", "data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_1h.csv"),
        },
        results_template="strategies/strategy_04/v1_2/results/{symbol}_1h_15m_{variant}",
        audit_columns=(
            "risk_zone_ratio",
            "one_hour_reference_open",
            "one_hour_reference_close",
        ),
        sweep_parameter="max_risk_zone_ratio",
        sweep_grid=tuple(round(1.5 + 0.25 * step, 2) for step in range(11)),  # 1.5 .. 4.0
        change_description=(
            "Filter A rejects reactions whose trigger close sits more than "
            "max_risk_zone_ratio zone-widths from the stop; Filter B rejects "
            "reactions opposing the latest completed one-hour candle. Both are "
            "independently switchable; this run is the "
            "'{variant}' ablation variant."
        ),
        warning=(
            "Historical research only. Version 1.2 is an experiment, not a replacement: "
            "the max_risk_zone_ratio threshold has not been validated (the 2.5 default was "
            "chosen in-sample) and Filter B is a hypothesis from a single reviewed trade. "
            "No configuration is approved for paper or live execution. FX runs additionally "
            "inherit every v1.1 FX caveat (TPO zones, midpoint data, modelled spread, "
            "equity-tuned bar-count parameters)."
        ),
    ),
}
