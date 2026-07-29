"""Reading a run's ledger and publishing its checks as a contract dataset."""

import json
from pathlib import Path

import pytest

from ai_trade.ledger_audit_datasets import (
    contract_multiplier_for,
    contract_multiplier_from_report,
    ledger_audit_entries,
    load_ledger_rows,
    merge_audit_datasets,
)
from ai_trade.visualization_contract import ContractError, build_trade_audit

REPO_ROOT = Path(__file__).resolve().parent.parent
S4_RESULT = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"
MGC_RESULT = (
    REPO_ROOT / "outputs" / "strategy_01" / "v3" / "mgc" / "runs" / "two_year_preliminary_2026-07-16"
)

LEDGER_HEADER = (
    "decision_timestamp,entry_timestamp,exit_timestamp,side,rrms_tier,quantity,"
    "entry_price,stop_price,target_price,exit_price,exit_reason,gross_pnl,costs,"
    "net_pnl,result_r,equity_after\n"
)
CLEAN_ROW = (
    "2021-06-21T18:15:00Z,2021-06-21T18:15:00Z,2021-06-22T14:15:00Z,short,0,227,"
    "420.66,421.32,420.01,421.36,stop,-158.90,2.27,-161.17,-1.0755,99838.83\n"
)


def _result_dir(tmp_path: Path, rows: str = CLEAN_ROW, report=None) -> Path:
    directory = tmp_path / "run"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fixed_trades.csv").write_text(LEDGER_HEADER + rows, encoding="utf-8")
    if report is not None:
        (directory / "backtest_report.json").write_text(json.dumps(report), encoding="utf-8")
    return directory


# --- reading the ledger -----------------------------------------------------


def test_ledger_rows_are_parsed_into_numbers_not_strings(tmp_path):
    rows = load_ledger_rows(_result_dir(tmp_path) / "fixed_trades.csv")
    assert len(rows) == 1
    assert rows[0].quantity == 227
    assert rows[0].net_pnl == pytest.approx(-161.17)
    assert rows[0].side == "short"


def test_every_recorded_run_has_a_readable_ledger():
    rows = load_ledger_rows(S4_RESULT / "fixed_trades.csv")
    assert rows, "the Strategy 04 fixture ledger is empty; later assertions would be vacuous"


# --- where the contract multiplier actually lives ---------------------------


def test_the_multiplier_is_read_from_assumptions():
    """This is where every futures run in this repository records it."""

    assert contract_multiplier_from_report({"assumptions": {"contract_multiplier": 10.0}}) == 10.0


def test_the_multiplier_is_also_read_from_backtest_configuration():
    report = {"backtest_configuration": {"contract_multiplier": 1.0}}
    assert contract_multiplier_from_report(report) == 1.0


def test_a_report_that_records_no_multiplier_defaults_to_one():
    """An unmultiplied instrument is the overwhelming default, and stating
    nothing is how these reports say so."""

    assert contract_multiplier_from_report({"strategy_id": "strategy_02"}) == 1.0


def test_a_missing_report_leaves_the_multiplier_unknown(tmp_path):
    """Absent evidence is not evidence of 1.0."""

    assert contract_multiplier_for(_result_dir(tmp_path)) is None


def test_an_unparseable_report_leaves_the_multiplier_unknown(tmp_path):
    directory = _result_dir(tmp_path)
    (directory / "backtest_report.json").write_text("{not json", encoding="utf-8")
    assert contract_multiplier_for(directory) is None


def test_a_non_numeric_multiplier_is_unknown_rather_than_one():
    assert contract_multiplier_from_report({"assumptions": {"contract_multiplier": "ten"}}) is None


def test_a_non_positive_multiplier_is_unknown_rather_than_one():
    assert contract_multiplier_from_report({"assumptions": {"contract_multiplier": 0}}) is None


def test_two_locations_that_disagree_leave_the_multiplier_unknown():
    """One report stating two multipliers cannot be resolved by preferring one."""

    report = {
        "assumptions": {"contract_multiplier": 10.0},
        "backtest_configuration": {"contract_multiplier": 1.0},
    }
    assert contract_multiplier_from_report(report) is None


def test_the_gold_run_reports_the_multiplier_its_trades_were_sized_with():
    assert contract_multiplier_for(MGC_RESULT) == 10.0


# --- building the entries ---------------------------------------------------


def test_entries_carry_ledger_trade_ids_in_ledger_order(tmp_path):
    directory = _result_dir(tmp_path, rows=CLEAN_ROW + CLEAN_ROW, report={"assumptions": {}})
    entries = ledger_audit_entries(directory, "run", "fixed")
    assert [entry["trade_id"] for entry in entries] == ["run:fixed:000001", "run:fixed:000002"]


def test_every_entry_carries_all_six_checks(tmp_path):
    directory = _result_dir(tmp_path, report={"assumptions": {}})
    entries = ledger_audit_entries(directory, "run", "fixed")
    assert [check["check_id"] for check in entries[0]["checks"]] == [
        "net_pnl",
        "equity_chain",
        "result_r",
        "exit_after_entry",
        "quantity",
        "level_sides",
    ]


def test_a_run_with_no_report_publishes_result_r_as_inconclusive(tmp_path):
    entries = ledger_audit_entries(_result_dir(tmp_path), "run", "fixed")
    result_r = next(c for c in entries[0]["checks"] if c["check_id"] == "result_r")
    assert result_r["passed"] is False
    assert "inconclusive" in result_r["expected"]


def test_a_corrupt_ledger_row_is_reported_not_swallowed(tmp_path):
    corrupt = CLEAN_ROW.replace(",-161.17,", ",-999.00,")
    directory = _result_dir(tmp_path, rows=corrupt, report={"assumptions": {}})
    entries = ledger_audit_entries(directory, "run", "fixed")
    failed = [c["check_id"] for c in entries[0]["checks"] if not c["passed"]]
    assert "net_pnl" in failed


# --- merging with Strategy 04's signal checks -------------------------------


def _ledger_entry(trade_id: str):
    return {
        "trade_id": trade_id,
        "checks": [{"check_id": "net_pnl", "passed": True, "expected": "1", "actual": "1"}],
    }


def test_a_run_with_no_signal_audit_publishes_the_ledger_checks_alone():
    datasets = merge_audit_datasets([_ledger_entry("r:fixed:000001")], [])
    assert [dataset.dataset_id for dataset in datasets] == ["trade_audit"]
    trade = datasets[0].payload["trades"][0]
    assert [check["check_id"] for check in trade["checks"]] == ["net_pnl"]


def test_strategy_04_signal_checks_join_the_same_entry():
    """One dataset per run, not two audits the dashboard has to reconcile."""

    signal = build_trade_audit(
        [
            {
                "trade_id": "r:fixed:000001",
                "trigger_timestamp": "2021-06-21T18:00:00Z",
                "checks": [
                    {"check_id": "stop_price", "passed": True, "expected": "1", "actual": "1"}
                ],
            }
        ]
    )
    datasets = merge_audit_datasets([_ledger_entry("r:fixed:000001")], [signal])
    trade = datasets[0].payload["trades"][0]
    assert [check["check_id"] for check in trade["checks"]] == ["net_pnl", "stop_price"]
    assert trade["trigger_timestamp"] == "2021-06-21T18:00:00Z"


def test_a_failing_signal_check_fails_the_merged_trade():
    signal = build_trade_audit(
        [
            {
                "trade_id": "r:fixed:000001",
                "checks": [
                    {"check_id": "session", "passed": False, "expected": "a", "actual": "b"}
                ],
            }
        ]
    )
    datasets = merge_audit_datasets([_ledger_entry("r:fixed:000001")], [signal])
    assert datasets[0].payload["trades"][0]["passed"] is False
    assert datasets[0].payload["summary"]["audit_failed"] == 1


def test_the_other_strategy_04_datasets_are_carried_through_in_order():
    from ai_trade.visualization_contract import build_audit_windows, build_zones

    zones = build_zones(
        [
            {
                "trade_id": "r:fixed:000001",
                "selected": {"zone_id": 1, "side": "demand", "lower": 1.0, "upper": 2.0},
            }
        ]
    )
    signal = build_trade_audit(
        [
            {
                "trade_id": "r:fixed:000001",
                "checks": [{"check_id": "session", "passed": True, "expected": "", "actual": ""}],
            }
        ]
    )
    windows = build_audit_windows(
        [
            {
                "trade_id": "r:fixed:000001",
                "one_hour": [
                    {
                        "timestamp": "2021-06-21T18:00:00Z",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 10,
                    }
                ],
            }
        ]
    )
    datasets = merge_audit_datasets([_ledger_entry("r:fixed:000001")], [zones, signal, windows])
    assert [dataset.dataset_id for dataset in datasets] == ["zones", "trade_audit", "audit_windows"]


def test_a_signal_check_for_a_trade_the_ledger_never_recorded_is_rejected():
    """Silently dropping it would publish an audit of a different ledger."""

    signal = build_trade_audit(
        [
            {
                "trade_id": "r:fixed:000009",
                "checks": [{"check_id": "session", "passed": True, "expected": "", "actual": ""}],
            }
        ]
    )
    with pytest.raises(ContractError):
        merge_audit_datasets([_ledger_entry("r:fixed:000001")], [signal])
