import json
from pathlib import Path

import pytest

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
        # Every field here is internally consistent, because the bundle this
        # fixture publishes is now audited: net = gross - costs, and
        # result_r = net / (|entry - stop| x quantity). The rounded -1.079
        # this carried before was off by 3e-3 and would fail the ledger's
        # own arithmetic -- which is the point of checking it.
        "420.66,421.32,420.01,421.36,stop,-158.90,2.27,-161.17,-1.0758,99838.83\n",
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
                "average_r": -1.0758,
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


# --- every run, not just Strategy 04, publishes a trade audit ---------------


def _bundle_datasets(result_dir: Path) -> dict:
    manifest = json.loads((result_dir / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    return {descriptor["dataset_id"]: descriptor for descriptor in manifest["datasets"]}


def _audit_payload(result_dir: Path) -> dict:
    descriptor = _bundle_datasets(result_dir)["trade_audit"]
    return json.loads((result_dir / "visualization" / descriptor["path"]).read_text(encoding="utf-8"))


def test_a_run_from_any_strategy_publishes_a_trade_audit(tmp_path):
    """The demo report's strategy_id is strategy_09_demo: not Strategy 04,
    and it still gets audited, because the ledger checks read the ledger."""

    _make_result(tmp_path / "good")
    backfill([tmp_path], dry_run=False)
    assert "trade_audit" in _bundle_datasets(tmp_path / "good")


def test_the_published_audit_covers_every_ledger_trade(tmp_path):
    _make_result(tmp_path / "good")
    backfill([tmp_path], dry_run=False)
    payload = _audit_payload(tmp_path / "good")
    assert [trade["trade_id"] for trade in payload["trades"]] == ["good:fixed:000001"]
    assert payload["summary"] == {"audit_passed": 1, "audit_failed": 0}


def test_a_ledger_that_contradicts_itself_is_published_as_failed(tmp_path):
    """A corrupt run must publish a failure, not be skipped or smoothed."""

    _make_result(tmp_path / "bad")
    ledger = tmp_path / "bad" / "fixed_trades.csv"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(",-161.17,", ",-99.99,"), encoding="utf-8")
    backfill([tmp_path], dry_run=False)
    payload = _audit_payload(tmp_path / "bad")
    assert payload["summary"]["audit_failed"] == 1
    failed = [c["check_id"] for c in payload["trades"][0]["checks"] if not c["passed"]]
    assert "net_pnl" in failed


def test_capabilities_separate_the_ledger_audit_from_the_signal_audit(tmp_path):
    _make_result(tmp_path / "good")
    backfill([tmp_path], dry_run=False)
    manifest = json.loads((tmp_path / "good" / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["capabilities"]["has_trade_audit"] is True
    assert manifest["capabilities"]["has_signal_audit"] is False


# --- the checks must be falsifiable ---------------------------------------
#
# Every one of these mutations is a defect a backtest could really produce,
# and each is applied to a ledger that is otherwise internally consistent
# and passes cleanly. A check that never fires is worse than no check: it
# reports "audited" over evidence it never examined.

TWO_ROWS = (
    "2021-06-21T18:15:00Z,2021-06-21T18:15:00Z,2021-06-22T14:15:00Z,short,0,227,"
    "420.66,421.32,420.01,421.36,stop,-158.90,2.27,-161.17,-1.0758,99838.83\n"
    "2021-06-23T14:00:00Z,2021-06-23T14:00:00Z,2021-06-23T19:00:00Z,long,0,100,"
    "400.00,399.00,401.00,401.00,target,100.00,1.00,99.00,0.99,99937.83\n"
)


def _make_two_row_result(directory: Path, report: dict = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _make_result(directory)
    (directory / "fixed_trades.csv").write_text(
        "decision_timestamp,entry_timestamp,exit_timestamp,side,rrms_tier,quantity,"
        "entry_price,stop_price,target_price,exit_price,exit_reason,gross_pnl,costs,"
        "net_pnl,result_r,equity_after\n" + TWO_ROWS,
        encoding="utf-8",
    )
    summary = json.loads((directory / "fixed_summary.json").read_text(encoding="utf-8"))
    summary.update({"trade_count": 2, "net_pnl": -62.17, "ending_equity": 99937.83})
    (directory / "fixed_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    if report is not None:
        (directory / "backtest_report.json").write_text(json.dumps(report), encoding="utf-8")


def _mutate_cell(directory: Path, row: int, column: str, value: str) -> None:
    lines = (directory / "fixed_trades.csv").read_text(encoding="utf-8").strip().split("\n")
    header = lines[0].split(",")
    cells = lines[row + 1].split(",")
    cells[header.index(column)] = value
    lines[row + 1] = ",".join(cells)
    (directory / "fixed_trades.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _swap_cells(directory: Path, row: int, left: str, right: str) -> None:
    lines = (directory / "fixed_trades.csv").read_text(encoding="utf-8").strip().split("\n")
    header = lines[0].split(",")
    cells = lines[row + 1].split(",")
    i, j = header.index(left), header.index(right)
    cells[i], cells[j] = cells[j], cells[i]
    lines[row + 1] = ",".join(cells)
    (directory / "fixed_trades.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _published_failures(result_dir: Path) -> set:
    payload = _audit_payload(result_dir)
    return {
        check["check_id"]
        for trade in payload["trades"]
        for check in trade["checks"]
        if not check["passed"]
    }


def test_the_two_row_ledger_the_mutations_start_from_passes_cleanly(tmp_path):
    """Without this, every mutation below could be passing vacuously."""

    _make_two_row_result(tmp_path / "clean")
    backfill([tmp_path], dry_run=False)
    assert _published_failures(tmp_path / "clean") == set()
    assert _audit_payload(tmp_path / "clean")["summary"] == {"audit_passed": 2, "audit_failed": 0}


@pytest.mark.parametrize(
    "mutate,expected_check",
    [
        (lambda d: _mutate_cell(d, 0, "costs", "3.27"), "net_pnl"),
        # Deliberately the FIRST row, not the last: the contract already
        # reconciles the final equity against the summary's ending_equity,
        # so a corrupted last row is caught before publication. A corrupted
        # middle row lands on the same ending equity and is invisible to
        # that reconciliation -- it is the gap equity_chain exists to close.
        (lambda d: _mutate_cell(d, 0, "equity_after", "100088.83"), "equity_chain"),
        (lambda d: _mutate_cell(d, 1, "result_r", "1.98"), "result_r"),
        (lambda d: _swap_cells(d, 1, "entry_timestamp", "exit_timestamp"), "exit_after_entry"),
        (lambda d: _mutate_cell(d, 1, "quantity", "0"), "quantity"),
        (lambda d: _swap_cells(d, 1, "stop_price", "target_price"), "level_sides"),
    ],
    ids=["net_pnl", "equity_chain", "result_r", "exit_after_entry", "quantity", "level_sides"],
)
def test_a_corrupted_ledger_is_caught_by_the_check_that_owns_the_field(
    tmp_path, mutate, expected_check
):
    _make_two_row_result(tmp_path / "mutated")
    mutate(tmp_path / "mutated")
    backfill([tmp_path], dry_run=False)
    assert expected_check in _published_failures(tmp_path / "mutated")


def test_swapping_a_stop_and_target_is_caught_by_nothing_else(tmp_path):
    """R:R is 1.0, so the risk distance is unchanged and result_r still
    reconciles. Only the level ordering shows the trade recorded its reward
    as its risk -- which is why that check exists separately."""

    _make_two_row_result(tmp_path / "swapped")
    _swap_cells(tmp_path / "swapped", 1, "stop_price", "target_price")
    backfill([tmp_path], dry_run=False)
    assert _published_failures(tmp_path / "swapped") == {"level_sides"}


def test_a_report_stating_two_different_multipliers_publishes_as_inconclusive(tmp_path):
    """Preferring one location would be assuming the answer the check asks."""

    _make_two_row_result(
        tmp_path / "conflicted",
        report={
            "strategy_id": "strategy_09_demo",
            "assumptions": {"contract_multiplier": 10.0},
            "backtest_configuration": {"contract_multiplier": 1.0},
        },
    )
    backfill([tmp_path], dry_run=False)
    payload = _audit_payload(tmp_path / "conflicted")
    assert payload["summary"]["audit_failed"] == 2
    check = next(c for c in payload["trades"][0]["checks"] if c["check_id"] == "result_r")
    assert check["passed"] is False
    assert "inconclusive" in check["expected"]
