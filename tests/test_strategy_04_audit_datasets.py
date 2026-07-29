from pathlib import Path

from ai_trade.strategy_04_audit_datasets import audit_datasets_for, report_bar_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
S4_RESULT = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"


def test_report_bar_paths_normalizes_recorded_windows_separators():
    """backtest_report.json records paths as written on the producing machine."""

    paths = report_bar_paths(
        {"data": {"one_hour_file": "data\\m\\spy_1h.csv", "fifteen_minute_file": "data\\m\\spy_15m.csv"}}
    )
    assert paths == ("data/m/spy_1h.csv", "data/m/spy_15m.csv")


def test_report_bar_paths_returns_none_when_not_recorded():
    """An audit must never guess which bars a run consumed."""

    assert report_bar_paths({"data": {}}) is None
    assert report_bar_paths({}) is None
    assert report_bar_paths(None) is None


def test_a_directory_that_is_not_a_strategy_04_run_yields_nothing(tmp_path):
    assert audit_datasets_for(tmp_path, REPO_ROOT) == []


def test_strategy_04_result_yields_the_three_datasets():
    datasets = audit_datasets_for(S4_RESULT, REPO_ROOT)
    assert [d.dataset_id for d in datasets] == ["zones", "trade_audit", "audit_windows"]
    assert [d.kind for d in datasets] == ["zones", "trade_audit", "candles"]


def test_audit_trade_ids_match_the_ledger_ids_in_order():
    """The dashboard joins on trade_id; a mismatch renders an empty audit."""

    from ai_trade.backfill_visualization_bundles import _build_variant_datasets

    ledger = _build_variant_datasets(S4_RESULT, "fixed", S4_RESULT.name)[0]
    expected = [trade["trade_id"] for trade in ledger.payload["trades"]]
    assert expected, "ledger produced no trades; the rest of this test would be vacuous"
    for dataset in audit_datasets_for(S4_RESULT, REPO_ROOT):
        assert [t["trade_id"] for t in dataset.payload["trades"]] == expected, dataset.dataset_id


def test_every_trade_appears_in_every_audit_dataset():
    datasets = {d.dataset_id: d.record_count for d in audit_datasets_for(S4_RESULT, REPO_ROOT)}
    assert len(set(datasets.values())) == 1, datasets
