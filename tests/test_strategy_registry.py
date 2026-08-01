"""The registry entry must agree with the legacy exports the pipeline reads.

These are drift guards, not behaviour tests: the v1.2 wrapper now derives its
exports from the registry, and the literal expectations pinned in
``test_backtest_strategy_04_v1_2_asset.py`` still hold, so together they prove
the registry entry encodes the same run the committed results came from.
"""

from pathlib import Path

from ai_trade.backtest_strategy_04_v1_2_asset import (
    SUPPORTED_SYMBOLS,
    VARIANTS,
    _EQUITY_DATA,
    _FX_DATA,
)
from ai_trade.strategy_registry import STRATEGIES, VERSIONS
from ai_trade.sweep_strategy_04_v1_2_risk_ratio import DEFAULT_THRESHOLDS

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = VERSIONS["strategy_04_v1_2"]


def test_variant_overrides_match_the_legacy_flag_tuples():
    assert tuple(SPEC.variants) == tuple(VARIANTS)
    for name, overrides in SPEC.variants.items():
        params = SPEC.params_type(**dict(overrides))
        assert (params.enable_filter_a, params.enable_filter_b) == VARIANTS[name], name


def test_symbol_tables_match_the_runner_exports():
    assert SPEC.supported_symbols == SUPPORTED_SYMBOLS
    assert dict(SPEC.equity_data) == _EQUITY_DATA
    assert dict(SPEC.fx_data) == _FX_DATA


def test_change_key_encodes_the_incumbent_exactly():
    """_published_condition scans for change_from_*; the key must be v1.2's."""
    assert SPEC.incumbent == "v1_1"
    assert SPEC.change_key == "change_from_v1_1"


def test_results_template_matches_the_committed_layout():
    assert SPEC.results_template.format(symbol="spy", variant="base") == (
        "strategies/strategy_04/v1_2/results/spy_1h_15m_base"
    )


def test_sweep_definition_matches_the_sweep_module():
    # Since Task A3 the sweep module re-exports the registry's grid; this
    # pins the historical export and the spec's literals together.
    assert SPEC.sweep_parameter == "max_risk_zone_ratio"
    assert SPEC.sweep_grid == DEFAULT_THRESHOLDS
    assert SPEC.sweep_default == 2.5


def test_every_spec_document_exists_on_disk():
    """A registry pointing at a missing spec is worse than no pointer."""
    for strategy in STRATEGIES.values():
        document = REPO_ROOT / strategy.spec_document
        assert document.is_file(), (
            f"{strategy.strategy_id}: spec_document {strategy.spec_document} missing"
        )


def test_versions_is_exactly_the_flattening_of_strategies():
    """VERSIONS is derived from STRATEGIES — one source of truth, same objects."""
    derived = {
        version.version_id: version
        for strategy in STRATEGIES.values()
        for version in strategy.versions
    }
    assert set(VERSIONS) == set(derived)
    for version_id, spec in VERSIONS.items():
        assert spec is derived[version_id], version_id


def test_every_version_belongs_to_the_strategy_that_registers_it():
    for strategy in STRATEGIES.values():
        for version in strategy.versions:
            assert version.strategy_id == strategy.strategy_id, version.version_id


def test_legacy_strategies_are_metadata_only():
    # Strategies 01-03 run through bespoke runners that predate the pipeline;
    # the registry records them without pretending it can run them.
    for legacy in ("strategy_01", "strategy_02", "strategy_03"):
        assert STRATEGIES[legacy].versions == (), legacy
    assert tuple(v.version_id for v in STRATEGIES["strategy_04"].versions) == (
        "strategy_04_v1_2",
    )
