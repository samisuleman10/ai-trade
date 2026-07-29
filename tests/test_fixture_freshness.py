"""The dashboard's audit fixtures must still agree with the ledgers they came from.

Strategy 04's deep-dive renders committed JSON fixtures rather than the
published visualization bundles, because the bundles do not yet carry the
`trade_audit`, `zones`, or `candles` datasets that view needs. That leaves two
sources of truth for the same run: rerunning a backtest updates the CSV ledger
and the bundle, but not the fixture, and the screen would keep showing the old
result with nothing to indicate it was stale.

Until the deep-dive consumes the API, these tests are what makes that drift
loud. A rerun that changes any recorded trade fails here, naming the fixture
that needs regenerating with `python -m ai_trade.build_strategy_04_fixture`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "dashboard" / "src" / "fixtures"
TOLERANCE = 1e-6

FIXTURE_PATHS = sorted(FIXTURE_DIR.glob("strategy_04_*.json"))


def _results_dir(fixture: dict) -> Path:
    version = fixture["run"]["strategy_version"]
    symbol = fixture["instrument"]["symbol"].lower()
    return REPO_ROOT / "strategies" / "strategy_04" / version / "results" / f"{symbol}_1h_15m"


def _ledger_rows(results_dir: Path) -> list[dict]:
    with (results_dir / "fixed_trades.csv").open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_at_least_one_fixture_is_present():
    """Guard the guard: a glob that silently matched nothing would pass everything."""

    assert FIXTURE_PATHS, f"no audit fixtures found in {FIXTURE_DIR}"


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_fixture_matches_its_ledger(fixture_path: Path):
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    results_dir = _results_dir(fixture)
    rows = _ledger_rows(results_dir)

    assert len(fixture["trades"]) == len(rows), (
        f"{fixture_path.name} has {len(fixture['trades'])} trades but "
        f"{results_dir.name}/fixed_trades.csv has {len(rows)}. Regenerate with "
        "python -m ai_trade.build_strategy_04_fixture"
    )

    for trade, row in zip(fixture["trades"], rows):
        where = f"{fixture_path.name} trade {trade['ordinal']}"
        assert trade["entry_timestamp"] == row["entry_timestamp"], where
        assert trade["exit_timestamp"] == row["exit_timestamp"], where
        assert trade["side"] == row["side"], where
        assert trade["exit_reason"] == row["exit_reason"], where
        for field in ("entry_price", "stop_price", "target_price", "exit_price", "result_r"):
            assert abs(trade[field] - float(row[field])) < TOLERANCE, f"{where}: {field}"


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_fixture_summary_matches_its_backtest_summary(fixture_path: Path):
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    results_dir = _results_dir(fixture)
    summary = json.loads((results_dir / "fixed_summary.json").read_text(encoding="utf-8"))

    assert fixture["summary"]["trade_count"] == summary["trade_count"]
    assert abs(fixture["summary"]["net_pnl"] - summary["net_pnl"]) < TOLERANCE
    assert abs(fixture["summary"]["ending_equity"] - summary["ending_equity"]) < TOLERANCE


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_audit_counts_agree_with_the_per_trade_results(fixture_path: Path):
    """A summary that disagrees with its own trades would misreport the audit."""

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    passed = sum(1 for trade in fixture["trades"] if trade["audit"]["passed"])
    failed = len(fixture["trades"]) - passed

    assert fixture["summary"]["audit_passed"] == passed
    assert fixture["summary"]["audit_failed"] == failed

    for trade in fixture["trades"]:
        expected = all(check["passed"] for check in trade["audit"]["checks"])
        assert trade["audit"]["passed"] == expected, (
            f"{fixture_path.name} trade {trade['ordinal']} reports "
            f"passed={trade['audit']['passed']} but its checks say {expected}"
        )
