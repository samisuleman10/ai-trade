"""Registry of strategies and their runnable versions.

Everything the pipeline needs that differs between versions lives in one
``VersionSpec``: the signal builder, the variant grid, the data caches, the
sweep definition and the report prose. The runner, sweep, ablation summary
and grid read the spec instead of each growing another version-named copy —
three hand-maintained symbol lists is how IWM, GLD and SLV came to be
backtested but silently absent from the summary table.

``StrategySpec`` sits one level above: it groups a strategy's versions under
its display metadata and spec document. ``VERSIONS`` is derived from
``STRATEGIES`` so there is exactly one source of truth, while every existing
``VERSIONS[...]`` lookup keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
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
    # When this version's rules were frozen, as a git-checkable timestamp with
    # the commit that froze them. Empty means "not established".
    rules_fixed: str = ""
    # Symbol -> when that instrument's data first entered the repository, for
    # symbols whose data arrived AFTER rules_fixed. Those symbols are a
    # cross-instrument holdout: a rule cannot be fitted to data the repository
    # did not hold. This is provenance, not opinion -- every entry is a git
    # log away from being checked, and the reports say so.
    #
    # It lives here because the ablation summary was claiming "every number is
    # in-sample" over five symbols for which that was false, and prose in one
    # renderer is exactly the kind of hand-maintained copy this registry
    # exists to abolish. Default empty is the conservative reading: a version
    # that has not established provenance is reported as fully in-sample.
    holdout_symbols: Mapping[str, str] = MappingProxyType({})
    # Where the holdout was evaluated against a committed decision rule, if it
    # has been. A holdout nobody scored is not evidence.
    holdout_report: str = ""

    def __post_init__(self) -> None:
        unknown = set(self.holdout_symbols) - set(self.supported_symbols)
        if unknown:
            # A holdout claim about a symbol this version never runs would put
            # an unfalsifiable sentence into every report it renders.
            raise ValueError(
                f"{self.version_id}: holdout_symbols names symbols this version "
                f"does not run: {sorted(unknown)}"
            )
        if self.holdout_symbols and not self.rules_fixed:
            raise ValueError(
                f"{self.version_id}: holdout_symbols is meaningless without "
                "rules_fixed -- 'after' needs a date to be after."
            )

    @property
    def supported_symbols(self) -> Tuple[str, ...]:
        """Derived from the caches so the list cannot drift from the data."""
        return tuple(self.equity_data) + tuple(self.fx_data)

    @property
    def in_sample_symbols(self) -> Tuple[str, ...]:
        """Everything not established as arriving after the rules were fixed."""
        return tuple(
            symbol for symbol in self.supported_symbols
            if symbol not in self.holdout_symbols
        )

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


@dataclass(frozen=True)
class StrategySpec:
    """One strategy family: display metadata plus its pipeline-runnable versions.

    ``versions`` holds only versions the generic pipeline can run. Strategies
    01-03 predate the pipeline and run through their own bespoke runners
    (``backtest_strategy_01`` and friends); they are registered with an empty
    ``versions`` tuple so the registry can answer "what strategies exist and
    where is each one specified" without pretending it can run them.
    """

    strategy_id: str
    title: str
    subtitle: str
    # Repo-relative path to the document that specifies the strategy's current
    # rules. A registry pointing at a missing spec is worse than no pointer,
    # so tests assert this file exists on disk.
    spec_document: str
    versions: Tuple[VersionSpec, ...] = ()


_STRATEGY_04_V1_2 = VersionSpec(
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
    # Filters A and B were specified in bffe4f2. Everything below arrived
    # afterwards, so neither filter could have been fitted to it.
    rules_fixed="2026-07-29 10:58 (bffe4f2, the v1.2 spec)",
    holdout_symbols=MappingProxyType({
        # The spot-FX downloader, 12h23m after the filters were specified.
        "EURUSD": "2026-07-29 23:17 (6c503e4)",
        "GBPUSD": "2026-07-29 23:17 (6c503e4)",
        # Cached two days later, to widen coverage rather than to test
        # anything -- which is why their holdout status went unnoticed until
        # GLD's Filter B row looked like a finding.
        "IWM": "2026-07-31 16:40 (55f381e)",
        "GLD": "2026-07-31 16:40 (55f381e)",
        "SLV": "2026-07-31 16:40 (55f381e)",
    }),
    holdout_report="strategies/strategy_04/v1_3/results/HOLDOUT_RESULT.md",
)


STRATEGIES: Dict[str, StrategySpec] = {
    # Strategies 01-03 are metadata-only entries: their published runs came
    # from bespoke runners that predate this pipeline, and retrofitting them
    # would risk the committed evidence for no gain. Their spec_document is
    # the newest version's strategy document.
    "strategy_01": StrategySpec(
        strategy_id="strategy_01",
        title="Strategy 01",
        subtitle="Bill Williams Alligator with Heikin Ashi confirmation",
        spec_document="strategies/strategy_01/v5/strategy.md",
        versions=(),
    ),
    "strategy_02": StrategySpec(
        strategy_id="strategy_02",
        title="Strategy 02",
        subtitle="One-hour Heikin Ashi Jaw-cross reversal with 15m confirmation",
        spec_document="strategies/strategy_02/v3/strategy.md",
        versions=(),
    ),
    "strategy_03": StrategySpec(
        strategy_id="strategy_03",
        title="Strategy 03",
        subtitle="Alligator mouth opening alone, no confirmation filters",
        spec_document="strategies/strategy_03/v1/strategy.md",
        versions=(),
    ),
    "strategy_04": StrategySpec(
        strategy_id="strategy_04",
        title="Strategy 04",
        subtitle="Causal 1H zones, 15m reaction entries",
        spec_document="strategies/strategy_04/v1_2/strategy.md",
        versions=(_STRATEGY_04_V1_2,),
    ),
}


def _versions_from_strategies(
    strategies: Mapping[str, StrategySpec],
) -> Dict[str, VersionSpec]:
    """Flatten every strategy's versions into the flat lookup the pipeline uses.

    Guards at import time rather than at first lookup: a version claiming a
    strategy_id its owner does not have, or two strategies claiming the same
    version_id, is a registry authoring error that should fail loudly before
    any run starts.
    """
    versions: Dict[str, VersionSpec] = {}
    for strategy in strategies.values():
        for spec in strategy.versions:
            if spec.strategy_id != strategy.strategy_id:
                raise ValueError(
                    f"{spec.version_id} claims strategy_id {spec.strategy_id!r} "
                    f"but is registered under {strategy.strategy_id!r}"
                )
            if spec.version_id in versions:
                raise ValueError(f"duplicate version_id {spec.version_id!r}")
            versions[spec.version_id] = spec
    return versions


# Derived, never authored: the pipeline modules keep reading VERSIONS[...],
# but the entries themselves live inside STRATEGIES above.
VERSIONS: Dict[str, VersionSpec] = _versions_from_strategies(STRATEGIES)
