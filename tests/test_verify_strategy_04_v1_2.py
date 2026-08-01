import ast
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_trade.verify_strategy_04_v1_2 import audit_columns, main, parity_against_v1_1


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_HOUR_START = datetime(2026, 1, 6, 13, 0, tzinfo=timezone.utc)


def _write_hours(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for i in range(3):
            writer.writerow([_stamp(_HOUR_START + timedelta(hours=i)), 100.0, 101.0, 99.0, 100.5, 1000.0])


_SIGNAL_ROW = {
    "decision_timestamp": "2026-01-06T14:45:00Z",
    "entry_timestamp": "2026-01-06T14:45:00Z",
    "side": "long",
    "stop_reference": "98.9",
    "zone_lower": "99.0",
    "zone_upper": "100.0",
    "trigger_close": "100.4",
    # one_hour_atr_timestamp is the reference bar's CLOSE time, so the
    # bar itself is the one stamped 13:00Z in the hours fixture.
    "one_hour_atr_timestamp": "2026-01-06T14:00:00Z",
    "risk_zone_ratio": "1.5000000000000004",
    "one_hour_reference_open": "100.0",
    "one_hour_reference_close": "100.5",
}


def _write_signals(path: Path, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_audit_columns_passes_on_consistent_rows(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(results, hours)
    assert report["rows"] == 1
    assert report["failures"] == []


def test_audit_columns_catches_wrong_ratio_and_wrong_reference(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    bad_ratio = dict(_SIGNAL_ROW, risk_zone_ratio="2.0")
    bad_reference = dict(_SIGNAL_ROW, one_hour_reference_close="999.0")
    _write_signals(results / "candidate_signals.csv", [bad_ratio, bad_reference])
    report = audit_columns(results, hours)
    assert report["rows"] == 2
    assert len(report["failures"]) == 2
    assert any("risk_zone_ratio" in failure for failure in report["failures"])
    assert any("reference" in failure for failure in report["failures"])


def test_parity_passes_when_only_new_columns_differ(tmp_path):
    v12 = tmp_path / "v12"
    v11 = tmp_path / "v11"
    v12.mkdir()
    v11.mkdir()
    old_row = {k: v for k, v in _SIGNAL_ROW.items()
               if k not in ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")}
    _write_signals(v11 / "candidate_signals.csv", [old_row])
    _write_signals(v12 / "candidate_signals.csv", [_SIGNAL_ROW])
    (v11 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (v12 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    report = parity_against_v1_1(v12, v11)
    assert report["signals_match"] is True
    assert report["trades_match"] is True


def test_parity_fails_on_any_shared_column_difference(tmp_path):
    v12 = tmp_path / "v12"
    v11 = tmp_path / "v11"
    v12.mkdir()
    v11.mkdir()
    old_row = {k: v for k, v in _SIGNAL_ROW.items()
               if k not in ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")}
    _write_signals(v11 / "candidate_signals.csv", [old_row])
    changed = dict(_SIGNAL_ROW, trigger_close="777.0")
    _write_signals(v12 / "candidate_signals.csv", [changed])
    (v11 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (v12 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    report = parity_against_v1_1(v12, v11)
    assert report["signals_match"] is False


def test_parity_fails_on_empty_vs_nonempty_signals(tmp_path):
    v12 = tmp_path / "v12"
    v11 = tmp_path / "v11"
    v12.mkdir()
    v11.mkdir()
    # v1.2 has empty signals, v1.1 has one signal
    (v12 / "candidate_signals.csv").write_text("", encoding="utf-8")
    old_row = {k: v for k, v in _SIGNAL_ROW.items()
               if k not in ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")}
    _write_signals(v11 / "candidate_signals.csv", [old_row])
    # Both have identical fixed_trades content
    (v11 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (v12 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    report = parity_against_v1_1(v12, v11)
    assert report["signals_match"] is False
    assert report["trades_match"] is True


# --- Finding 2: vacuous-pass guards ---------------------------------------


def test_parity_non_empty_false_when_v1_1_signals_are_empty(tmp_path):
    v12 = tmp_path / "v12"
    v11 = tmp_path / "v11"
    v12.mkdir()
    v11.mkdir()
    (v12 / "candidate_signals.csv").write_text("", encoding="utf-8")
    (v11 / "candidate_signals.csv").write_text("", encoding="utf-8")
    (v11 / "fixed_trades.csv").write_text("", encoding="utf-8")
    (v12 / "fixed_trades.csv").write_text("", encoding="utf-8")
    report = parity_against_v1_1(v12, v11)
    # Empty-vs-empty trivially "matches" -- that must not be enough to pass.
    assert report["signals_match"] is True
    assert report["trades_match"] is True
    assert report["non_empty"] is False


def test_parity_non_empty_true_when_v1_1_has_signals(tmp_path):
    v12 = tmp_path / "v12"
    v11 = tmp_path / "v11"
    v12.mkdir()
    v11.mkdir()
    old_row = {k: v for k, v in _SIGNAL_ROW.items()
               if k not in ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")}
    _write_signals(v11 / "candidate_signals.csv", [old_row])
    _write_signals(v12 / "candidate_signals.csv", [_SIGNAL_ROW])
    (v11 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (v12 / "fixed_trades.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    report = parity_against_v1_1(v12, v11)
    assert report["non_empty"] is True


def test_main_fails_on_zero_row_candidate_signals(tmp_path, monkeypatch):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    (results / "candidate_signals.csv").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "verify_strategy_04_v1_2", "--results", str(results), "--one-hour", str(hours),
    ])
    exit_code = main()
    assert exit_code == 1
    report = json.loads((results / "verification_report.json").read_text(encoding="utf-8"))
    assert report["column_audit"]["rows"] == 0
    assert report["passed"] is False


def test_main_still_passes_on_healthy_non_empty_results(tmp_path, monkeypatch):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    monkeypatch.setattr(sys, "argv", [
        "verify_strategy_04_v1_2", "--results", str(results), "--one-hour", str(hours),
    ])
    exit_code = main()
    assert exit_code == 0
    report = json.loads((results / "verification_report.json").read_text(encoding="utf-8"))
    assert report["passed"] is True


def test_main_requires_non_empty_parity_when_v1_1_given(tmp_path, monkeypatch):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    v1_1 = tmp_path / "v1_1"
    results.mkdir()
    v1_1.mkdir()
    (results / "candidate_signals.csv").write_text("", encoding="utf-8")
    (v1_1 / "candidate_signals.csv").write_text("", encoding="utf-8")
    (results / "fixed_trades.csv").write_text("", encoding="utf-8")
    (v1_1 / "fixed_trades.csv").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "verify_strategy_04_v1_2", "--results", str(results), "--one-hour", str(hours),
        "--v1-1", str(v1_1),
    ])
    exit_code = main()
    assert exit_code == 1
    report = json.loads((results / "verification_report.json").read_text(encoding="utf-8"))
    assert report["parity"]["signals_match"] is True
    assert report["parity"]["trades_match"] is True
    assert report["parity"]["non_empty"] is False
    assert report["passed"] is False


# --- Finding 3: causality and filter-satisfaction checks ------------------


def test_audit_columns_flags_causality_violation(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    # Decision made before the recorded reference bar even closed.
    bad_causality = dict(_SIGNAL_ROW, decision_timestamp="2026-01-06T13:30:00Z")
    _write_signals(results / "candidate_signals.csv", [bad_causality])
    report = audit_columns(results, hours)
    assert len(report["failures"]) == 1
    assert "causal" in report["failures"][0].lower() or "decision_timestamp" in report["failures"][0]


def test_audit_columns_passes_causality_on_clean_row(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(results, hours)
    assert report["failures"] == []


def test_audit_columns_flags_filter_a_violation(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    # Recorded risk_zone_ratio is 1.5; a threshold of 1.0 must be violated.
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(results, hours, enabled_filters={"a"}, max_risk_zone_ratio=1.0)
    assert len(report["failures"]) == 1
    assert "risk_zone_ratio" in report["failures"][0]


def test_audit_columns_passes_filter_a_within_bound(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(results, hours, enabled_filters={"a"}, max_risk_zone_ratio=2.5)
    assert report["failures"] == []


def test_audit_columns_flags_filter_b_violation(tmp_path):
    # A bearish reference bar (close < open) so the recorded reference
    # columns can genuinely match the actual bar while still disagreeing
    # with a "long" side -- isolates the filter-B check from the
    # already-covered recompute check.
    hours = tmp_path / "hours.csv"
    with hours.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerow([_stamp(_HOUR_START), 100.0, 101.0, 99.0, 99.5, 1000.0])
    results = tmp_path / "results"
    results.mkdir()
    bad_direction = dict(
        _SIGNAL_ROW,
        one_hour_reference_open="100.0",
        one_hour_reference_close="99.5",
    )
    _write_signals(results / "candidate_signals.csv", [bad_direction])
    report = audit_columns(results, hours, enabled_filters={"b"})
    assert len(report["failures"]) == 1
    assert "direction" in report["failures"][0].lower() or "side" in report["failures"][0].lower()


def test_audit_columns_passes_filter_b_agreement(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(results, hours, enabled_filters={"b"})
    assert report["failures"] == []


def test_audit_columns_clean_row_passes_with_both_filters_enabled(tmp_path):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    report = audit_columns(
        results, hours, enabled_filters={"a", "b"}, max_risk_zone_ratio=2.5
    )
    assert report["failures"] == []


def test_main_variant_maps_to_enabled_filters(tmp_path, monkeypatch):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    monkeypatch.setattr(sys, "argv", [
        "verify_strategy_04_v1_2", "--results", str(results), "--one-hour", str(hours),
        "--variant", "a", "--max-risk-zone-ratio", "1.0",
    ])
    exit_code = main()
    assert exit_code == 1
    report = json.loads((results / "verification_report.json").read_text(encoding="utf-8"))
    assert any("risk_zone_ratio" in failure for failure in report["column_audit"]["failures"])


# --- The independence property, enforced mechanically ---------------------
#
# The audit's entire value is that it re-derives filter decisions from
# recorded CSV columns without asking the implementation. A comment saying
# "keep this independent" is not enforcement; parsing the module's imports is.


def test_audit_rules_import_no_strategy_code():
    import ai_trade.audit_rules_v1_2 as audit_rules

    source = Path(audit_rules.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import ("from . import x") could smuggle in strategy
            # code without naming ai_trade, so it is banned outright.
            assert node.level == 0, "audit_rules_v1_2 must not use relative imports"
            imported_modules.append(node.module or "")
    forbidden = (
        "strategy_04_v1_2",
        "strategy_04_causal_loop",
        "strategy_04_v1_1",
        "strategy_registry",
    )
    for module_name in imported_modules:
        for banned in forbidden:
            assert banned not in module_name, (
                f"audit_rules_v1_2 imports {module_name!r}: an audit that asks "
                f"the implementation whether the implementation was right "
                f"proves nothing"
            )
        # Stronger than the named ban: the audit needs only the standard
        # library, so any ai_trade import at all is a red flag.
        assert not module_name.startswith("ai_trade"), (
            f"audit_rules_v1_2 imports {module_name!r}; it must stay "
            f"stdlib-only to remain independent of the code it audits"
        )


def test_main_base_variant_ignores_filter_thresholds(tmp_path, monkeypatch):
    hours = tmp_path / "hours.csv"
    _write_hours(hours)
    results = tmp_path / "results"
    results.mkdir()
    _write_signals(results / "candidate_signals.csv", [_SIGNAL_ROW])
    monkeypatch.setattr(sys, "argv", [
        "verify_strategy_04_v1_2", "--results", str(results), "--one-hour", str(hours),
        "--variant", "base", "--max-risk-zone-ratio", "1.0",
    ])
    exit_code = main()
    assert exit_code == 0
