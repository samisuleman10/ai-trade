import json
from pathlib import Path

from ai_trade.publish_run import publish_result_directory

from tests.test_backfill_visualization_bundles import _make_result


def test_publishing_a_finished_result_directory_creates_a_bundle(tmp_path):
    _make_result(tmp_path / "run")
    bundle = publish_result_directory(tmp_path / "run")
    assert bundle is not None
    assert (bundle / "manifest.json").exists()


def test_publishing_returns_none_when_requirements_are_missing(tmp_path):
    (tmp_path / "bare").mkdir()
    assert publish_result_directory(tmp_path / "bare") is None


def test_publishing_never_raises_when_a_trade_row_is_malformed(tmp_path):
    # Required files and a valid report are present -- publication gets past
    # the early "missing requirements" check -- but a required ledger field
    # is missing from the CSV, which is a contract violation deeper in the
    # pipeline (build_trade_ledger raises ContractError). The constraint
    # this is guarding is explicit: a failed export must never raise into
    # the caller, only report None, so a bad trade row can never take down
    # a caller that just finished writing real results.
    directory = tmp_path / "malformed"
    _make_result(directory)
    (directory / "fixed_trades.csv").write_text(
        "decision_timestamp,entry_timestamp,exit_timestamp,side\n"
        "2021-06-21T18:15:00Z,2021-06-21T18:15:00Z,2021-06-22T14:15:00Z,short\n",
        encoding="utf-8",
    )
    assert publish_result_directory(directory) is None


def test_a_live_publish_carries_the_same_ledger_audit_as_the_backfill(tmp_path):
    """Re-running a backtest must not replace an audited bundle with an
    unaudited one."""

    _make_result(tmp_path / "run")
    bundle = publish_result_directory(tmp_path / "run")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert "trade_audit" in [d["dataset_id"] for d in manifest["datasets"]]
    assert manifest["capabilities"]["has_trade_audit"] is True
