import json
from pathlib import Path

from ai_trade.backfill_visualization_bundles import (
    backfill,
    bundle_id_for,
    discover_results,
    run_identity,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_result(directory: Path, with_report: bool = True) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fixed_trades.csv").write_text(
        "decision_timestamp,entry_timestamp,exit_timestamp,side,rrms_tier,quantity,"
        "entry_price,stop_price,target_price,exit_price,exit_reason,gross_pnl,costs,"
        "net_pnl,result_r,equity_after\n"
        "2021-06-21T18:15:00Z,2021-06-21T18:15:00Z,2021-06-22T14:15:00Z,short,0,227,"
        "420.66,421.32,420.01,421.36,stop,-158.90,2.27,-161.17,-1.079,99838.83\n",
        encoding="utf-8",
    )
    (directory / "fixed_summary.json").write_text(
        json.dumps(
            {
                "trade_count": 1,
                "wins": 0,
                "losses": 1,
                "win_rate": 0.0,
                "net_pnl": -161.17,
                "ending_equity": 99838.83,
                "profit_factor": 0.0,
                "average_r": -1.079,
                "max_drawdown": 161.17,
                "long_trades": 0,
                "short_trades": 1,
                "exit_reasons": {"stop": 1},
            }
        ),
        encoding="utf-8",
    )
    if with_report:
        (directory / "backtest_report.json").write_text(
            json.dumps({"strategy_id": "strategy_09_demo", "symbol": "SPY", "mode": "historical_backtest_only"}),
            encoding="utf-8",
        )


def test_discovery_finds_directories_holding_both_required_files(tmp_path):
    _make_result(tmp_path / "good")
    (tmp_path / "empty").mkdir()
    assert discover_results([tmp_path]) == [tmp_path / "good"]


def test_identity_is_read_from_the_report_not_guessed_from_the_path(tmp_path):
    _make_result(tmp_path / "whatever_folder_name")
    identity = run_identity(tmp_path / "whatever_folder_name")
    assert identity["strategy_id"] == "strategy_09_demo"
    assert identity["symbol"] == "SPY"


def test_a_result_without_a_report_is_skipped_with_a_reason(tmp_path):
    _make_result(tmp_path / "no_report", with_report=False)
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 0
    assert report["skipped"] == 1
    assert "no_report" in str(report["reasons"])


def test_backfill_publishes_a_readable_bundle(tmp_path):
    _make_result(tmp_path / "good")
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 1
    manifest = json.loads((tmp_path / "good" / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["strategy_id"] == "strategy_09_demo"
    assert manifest["status"] == "complete"


# --- a missing ending_equity must not be papered over ---
#
# starting_equity was recovered as ``ending_equity - net_pnl`` with both
# defaulting to 0.0. A summary with no ending_equity therefore published
# ``-net_pnl`` as the run's equity anchor -- and because the contract's
# reconciliation guard only ran ``if ending_equity is not None``, the same
# absence also switched off the check that would have caught it.


def _summary_without(directory: Path, field: str) -> None:
    summary = json.loads((directory / "fixed_summary.json").read_text(encoding="utf-8"))
    del summary[field]
    (directory / "fixed_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_a_summary_with_no_ending_equity_is_skipped_with_a_reason(tmp_path):
    _make_result(tmp_path / "no_ending_equity")
    _summary_without(tmp_path / "no_ending_equity", "ending_equity")
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 0
    assert report["skipped"] == 1
    assert "ending_equity" in str(report["reasons"])
    assert not (tmp_path / "no_ending_equity" / "visualization").exists()


def test_a_summary_with_no_net_pnl_is_skipped_with_a_reason(tmp_path):
    """Without net_pnl the same subtraction silently reports a flat run."""

    _make_result(tmp_path / "no_net_pnl")
    _summary_without(tmp_path / "no_net_pnl", "net_pnl")
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 0
    assert report["skipped"] == 1
    assert "net_pnl" in str(report["reasons"])


def test_dry_run_writes_nothing(tmp_path):
    _make_result(tmp_path / "good")
    report = backfill([tmp_path], dry_run=True)
    assert report["published"] == 1
    assert not (tmp_path / "good" / "visualization").exists()


def test_real_repository_results_are_discovered():
    found = discover_results([REPO_ROOT / "outputs", REPO_ROOT / "strategies"])
    assert len(found) >= 40


# --- bundle_id: the collision-fix regression coverage ---
#
# Task 1 set bundle_id = run_id = the result directory's basename. Measured
# on the real repository, 49 result directories share only 40 unique
# basenames (e.g. every Strategy 04 result dir is named e.g. "spy_1h_15m"
# under both v1/ and v1_1/). A basename-derived bundle_id silently drops
# nine runs from the catalog. bundle_id_for() must derive a unique id from
# the full path instead.


def test_bundle_id_distinguishes_directories_that_share_a_basename(tmp_path):
    v1 = tmp_path / "strategy_04" / "v1" / "results" / "spy_1h_15m"
    v1_1 = tmp_path / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"
    v1.mkdir(parents=True)
    v1_1.mkdir(parents=True)
    assert bundle_id_for(v1, repo_root=tmp_path) != bundle_id_for(v1_1, repo_root=tmp_path)


def test_bundle_id_is_a_slug_of_the_repo_relative_path(tmp_path):
    result_dir = tmp_path / "strategies" / "strategy_02" / "v1_5" / "results" / "qqq_backtest"
    result_dir.mkdir(parents=True)
    bundle_id = bundle_id_for(result_dir, repo_root=tmp_path)
    assert "\\" not in bundle_id
    assert "/" not in bundle_id
    assert "." not in bundle_id
    assert "strategy_02" in bundle_id
    assert "qqq_backtest" in bundle_id


def test_bundle_id_is_unique_across_every_real_discovered_directory():
    found = discover_results([REPO_ROOT / "outputs", REPO_ROOT / "strategies"])
    ids = [bundle_id_for(directory) for directory in found]
    assert len(set(ids)) == len(ids)


def test_published_bundles_use_the_path_derived_bundle_id_not_the_run_id(tmp_path):
    a = tmp_path / "strategy_x" / "v1" / "results" / "same_name"
    b = tmp_path / "strategy_x" / "v2" / "results" / "same_name"
    _make_result(a)
    _make_result(b)
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 2
    manifest_a = json.loads((a / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    manifest_b = json.loads((b / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_a["bundle_id"] != manifest_b["bundle_id"]
    # run_id stays the human-readable directory name on both.
    assert manifest_a["run"]["run_id"] == "same_name"
    assert manifest_b["run"]["run_id"] == "same_name"
