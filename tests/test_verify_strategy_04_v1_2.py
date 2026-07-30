import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_trade.verify_strategy_04_v1_2 import audit_columns, parity_against_v1_1


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
