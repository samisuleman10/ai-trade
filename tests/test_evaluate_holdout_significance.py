"""The holdout evaluator is only trustworthy if it reproduces the July record.

`HOLDOUT_RESULT.md` was written on 30 July from arithmetic that lived nowhere
but the session that produced it. Re-deriving that table from the committed
trades is what licenses using the same script on new instruments: if it agreed
with itself but disagreed with the published verdicts, the new rows would be
measuring the new script rather than the strategy.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluate_holdout_significance import (  # noqa: E402
    collect,
    evaluate,
    t_critical_95,
)

RESULTS = REPO_ROOT / "strategies" / "strategy_04" / "v1_2" / "results"

# Student's two-sided 95% critical values, from standard tables. df=3 is the
# value the v1.3 spec cites when explaining why a flat 2.0 once marked a
# four-trade run conclusive.
PUBLISHED_CRITICAL_VALUES = {3: 3.182, 18: 2.101, 24: 2.064, 30: 2.042, 40: 2.021, 60: 2.000}


@pytest.mark.parametrize("df,expected", sorted(PUBLISHED_CRITICAL_VALUES.items()))
def test_critical_values_match_published_tables(df, expected):
    assert t_critical_95(df) == pytest.approx(expected, abs=0.0015)


def test_critical_value_grows_as_the_sample_shrinks():
    """The whole reason the rule forbids a flat 2.0 bar."""
    assert t_critical_95(3) > t_critical_95(18) > t_critical_95(200) > 1.95


def test_a_single_trade_is_not_a_verdict():
    """One trade has no dispersion; reporting it as significant is the trap."""
    assert evaluate([1.0]) is None
    assert evaluate([]) is None


# The published FX table: (symbol, variant) -> (trades, average R, t, rule).
PUBLISHED_FX = {
    ("GBPUSD", "ab"): (148, -0.2535, -3.11, "abandon"),
    ("GBPUSD", "a"): (231, -0.1954, -2.97, "abandon"),
    ("GBPUSD", "b"): (175, -0.1966, -2.60, "abandon"),
    ("EURUSD", "ab"): (119, -0.2016, -2.20, "abandon"),
    ("EURUSD", "b"): (141, -0.1797, -2.13, "abandon"),
    ("GBPUSD", "base"): (260, -0.1192, -1.91, "neither"),
    ("EURUSD", "a"): (218, -0.0928, -1.37, "neither"),
    ("EURUSD", "base"): (243, -0.0728, -1.13, "neither"),
}


def test_reproduces_every_published_fx_row():
    rows = {
        (symbol, variant): verdict
        for symbol, variant, verdict in collect(RESULTS, ("EURUSD", "GBPUSD"), ("base", "a", "b", "ab"))
    }
    assert set(rows) == set(PUBLISHED_FX)
    for key, (trades, average_r, t, rule) in PUBLISHED_FX.items():
        got = rows[key]
        assert got["trades"] == trades, key
        assert got["average_r"] == pytest.approx(average_r, abs=5e-5), key
        assert got["t"] == pytest.approx(t, abs=5e-3), key
        assert got["rule"] == rule, key


def test_the_metals_holdout_settles_nothing():
    """Zero of twelve fire -- including GLD's +$1,912 Filter B row."""
    rows = collect(RESULTS, ("IWM", "GLD", "SLV"), ("base", "a", "b", "ab"))
    assert len(rows) == 12
    assert all(verdict["rule"] == "neither" for _, _, verdict in rows)


def test_gld_filter_b_is_far_below_the_bar_it_would_have_to_clear():
    """The number that looked like the strongest result in the grid."""
    (_, _, verdict), = [
        row for row in collect(RESULTS, ("GLD",), ("b",))
    ]
    assert verdict["trades"] == 19
    assert verdict["average_r"] == pytest.approx(0.2037, abs=5e-5)
    assert verdict["t"] == pytest.approx(0.89, abs=5e-3)
    assert verdict["t"] < verdict["critical"]
    # Underpowered by more than 3x: the sample could not have resolved the
    # effect it appears to show.
    assert verdict["detectable_edge"] > 3 * verdict["average_r"]


def test_evaluator_imports_no_strategy_code():
    """Same independence the audit rules keep: it must not ask the strategy.

    A significance test that obtained its inputs by calling the implementation
    would be scoring the implementation's opinion of itself.
    """
    import ast

    source = (REPO_ROOT / "scripts" / "evaluate_holdout_significance.py").read_text(
        encoding="utf-8"
    )
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import"
            assert not (node.module or "").startswith("ai_trade"), node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("ai_trade"), alias.name
