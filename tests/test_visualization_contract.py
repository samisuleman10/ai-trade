import json

import pytest

from ai_trade.visualization_contract import (
    ContractError,
    SCHEMA_VERSION,
    _validate_relative_path,
    build_audit_windows,
    build_performance,
    build_run_summary,
    build_trade_audit,
    build_trade_ledger,
    build_zones,
    publish_bundle,
    read_manifest,
)


def _rows():
    return [
        {
            "decision_timestamp": "2021-06-21T18:15:00Z",
            "entry_timestamp": "2021-06-21T18:15:00Z",
            "exit_timestamp": "2021-06-22T14:15:00Z",
            "side": "short",
            "rrms_tier": "0",
            "quantity": "227",
            "entry_price": "420.66",
            "stop_price": "421.32",
            "target_price": "420.01",
            "exit_price": "421.36",
            "exit_reason": "stop",
            "gross_pnl": "-158.90",
            "costs": "2.27",
            "net_pnl": "-161.17",
            "result_r": "-1.079",
            "equity_after": "99838.83",
        },
        {
            "decision_timestamp": "2021-08-03T14:30:00Z",
            "entry_timestamp": "2021-08-03T14:30:00Z",
            "exit_timestamp": "2021-08-03T15:45:00Z",
            "side": "long",
            "rrms_tier": "1",
            "quantity": "177",
            "entry_price": "437.81",
            "stop_price": "435.84",
            "target_price": "439.78",
            "exit_price": "439.73",
            "exit_reason": "target",
            "gross_pnl": "340.49",
            "costs": "1.77",
            "net_pnl": "338.72",
            "result_r": "0.972",
            "equity_after": "100177.55",
        },
    ]


def _summary():
    return {
        "trade_count": 2,
        "wins": 1,
        "losses": 1,
        "win_rate": 0.5,
        "net_pnl": 177.55,
        "ending_equity": 100177.55,
        "profit_factor": 2.1,
        "average_r": -0.0535,
        "max_drawdown": 161.17,
        "long_trades": 1,
        "short_trades": 1,
        "exit_reasons": {"stop": 1, "target": 1},
    }


def _identity():
    return {
        "run_id": "demo_run",
        "strategy_id": "strategy_04",
        "strategy_version": "v1_1",
        "symbol": "SPY",
        "mode": "historical_backtest",
    }


def test_trade_ids_are_deterministic_and_ordinal():
    ledger = build_trade_ledger(_rows(), "fixed", "demo_run")
    ids = [trade["trade_id"] for trade in ledger.payload["trades"]]
    assert ids == ["demo_run:fixed:000001", "demo_run:fixed:000002"]


def test_trade_ledger_reports_record_count_and_bounds():
    ledger = build_trade_ledger(_rows(), "fixed", "demo_run")
    assert ledger.record_count == 2
    assert ledger.first_timestamp == "2021-06-21T18:15:00Z"
    assert ledger.last_timestamp == "2021-08-03T14:30:00Z"


def test_performance_anchors_starting_equity_then_follows_trades():
    perf = build_performance(_rows(), _summary(), "fixed", 100000.0)
    points = perf.payload["points"]
    assert points[0]["equity"] == 100000.0
    assert points[-1]["equity"] == 100177.55


def test_performance_points_carry_no_trade_id():
    """build_performance has no run_id, so it cannot construct a ledger
    trade_id (``<run_id>:<variant>:<ordinal>``) and always writes None.

    This assertion used to read ``== "demo_run:fixed:000002" or is None``,
    which the implementation satisfied unconditionally via the second
    branch -- a test that could not fail. Callers needing ledger-matching
    ids get them from build_trade_ledger; if that ever changes here, this
    test should fail and be updated deliberately.
    """

    perf = build_performance(_rows(), _summary(), "fixed", 100000.0)
    points = perf.payload["points"]
    assert [point["trade_id"] for point in points] == [None, None, None]


def test_performance_rejects_summary_disagreeing_with_ledger():
    bad = dict(_summary(), ending_equity=999999.0)
    with pytest.raises(ContractError):
        build_performance(_rows(), bad, "fixed", 100000.0)


def test_performance_rejects_a_summary_with_no_ending_equity():
    """The reconciliation guard used to switch itself off when the value it
    reconciles against was absent -- so the one summary that most needed
    checking was the one that skipped the check entirely.
    """

    bad = dict(_summary())
    del bad["ending_equity"]
    with pytest.raises(ContractError):
        build_performance(_rows(), bad, "fixed", 100000.0)


def test_performance_rejects_a_null_ending_equity():
    bad = dict(_summary(), ending_equity=None)
    with pytest.raises(ContractError):
        build_performance(_rows(), bad, "fixed", 100000.0)


def test_publish_writes_manifest_last_and_hashes_every_sidecar(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    bundle = publish_bundle(tmp_path, _identity(), datasets, {"sizing_variants": ["fixed"]}, [])
    manifest = read_manifest(bundle)
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["status"] == "complete"
    assert manifest["execution_authority"] == "none"
    assert len(manifest["datasets"]) == 2
    for descriptor in manifest["datasets"]:
        assert len(descriptor["sha256"]) == 64
        sidecar = bundle / descriptor["path"]
        assert sidecar.exists()


def test_publish_refuses_a_bundle_without_trades_and_performance(tmp_path):
    only_trades = [build_trade_ledger(_rows(), "fixed", "demo_run")]
    with pytest.raises(ContractError):
        publish_bundle(tmp_path, _identity(), only_trades, {}, [])


def test_publish_rejects_a_dataset_path_escaping_the_bundle(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    datasets[0].path = "../escape.json"
    with pytest.raises(ContractError):
        publish_bundle(tmp_path, _identity(), datasets, {}, [])


# Rejecting traversal on Windows is a stated constraint of this contract,
# but only the POSIX form ("../..") was ever exercised. Windows has several
# escape shapes that a "/"-only check would wave straight through.
TRAVERSAL_PATHS = [
    "C:\\x",              # absolute, drive-qualified
    "C:x",                # drive-relative: resolves against C:'s current dir
    "\\\\server\\share\\x",  # UNC path to another host
    "data\\..\\..\\x",    # backslash-separated traversal
    "..\\..\\..\\Windows\\System32\\config\\SAM",
    "\\Windows\\x",       # root-relative on the current drive
    "../../../etc/passwd",  # the POSIX form, kept for symmetry
]


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
def test_publish_rejects_windows_traversal_forms(tmp_path, bad_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    datasets[0].path = bad_path
    with pytest.raises(ContractError):
        publish_bundle(tmp_path, _identity(), datasets, {}, [])
    # Validation runs before anything touches disk, so nothing was written.
    assert not (tmp_path / "visualization" / "data").exists()


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
def test_string_validation_alone_rejects_windows_traversal_forms(bad_path):
    """Assert the string layer directly, not just the published outcome.

    publish_bundle also resolves the joined path and compares it against
    the bundle root, so most of these forms are refused twice. Testing only
    through publish_bundle would let the string checks rot silently behind
    that second guard -- and the second guard does not cover every form.
    ``C:x`` is drive-relative: pathlib joins it onto a same-drive parent by
    concatenation, so it lands INSIDE the bundle and the resolve-and-compare
    check never fires. The drive-letter rejection here is the only thing
    stopping it.
    """

    with pytest.raises(ContractError):
        _validate_relative_path(bad_path)


def test_republishing_replaces_the_previous_manifest(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    publish_bundle(tmp_path, _identity(), datasets, {}, [])
    bundle = publish_bundle(tmp_path, _identity(), datasets, {}, [])
    manifest = read_manifest(bundle)
    assert manifest["run"]["run_id"] == "demo_run"


def test_read_manifest_rejects_a_directory_with_no_manifest(tmp_path):
    with pytest.raises(ContractError):
        read_manifest(tmp_path / "visualization")


# --- zones, trade_audit and audit_windows (Phase 2 audit datasets) ---


def _audit_entry(trade_id="run:fixed:000001", passed=True):
    return {
        "trade_id": trade_id,
        "trigger_timestamp": "2021-08-03T14:15:00Z",
        "checks": [
            {"check_id": "causality_atr", "passed": passed, "expected": "before", "actual": "ok"},
        ],
    }


def _zone_entry(trade_id="run:fixed:000001"):
    return {
        "trade_id": trade_id,
        "selected": {
            "zone_id": 39,
            "side": "demand",
            "lower": 437.0,
            "upper": 437.9,
            "qualified_timestamp": "2021-08-03T13:00:00Z",
            "score": 2,
        },
        "competing": [],
    }


def test_build_trade_audit_reports_pass_and_fail_counts():
    dataset = build_trade_audit([_audit_entry(), _audit_entry("run:fixed:000002", passed=False)])
    assert dataset.kind == "trade_audit"
    assert dataset.dataset_id == "trade_audit"
    assert dataset.record_count == 2
    assert dataset.payload["summary"] == {"audit_passed": 1, "audit_failed": 1}


def test_build_trade_audit_derives_passed_from_its_own_checks():
    """A stored `passed` flag that disagreed with the checks would misreport the audit."""

    dataset = build_trade_audit([_audit_entry(passed=False)])
    assert dataset.payload["trades"][0]["passed"] is False


def test_build_trade_audit_rejects_a_trade_with_no_checks():
    with pytest.raises(ContractError):
        build_trade_audit([{"trade_id": "run:fixed:000001", "trigger_timestamp": "x", "checks": []}])


def test_build_trade_audit_rejects_duplicate_trade_ids():
    with pytest.raises(ContractError):
        build_trade_audit([_audit_entry(), _audit_entry()])


def test_build_zones_requires_a_selected_zone():
    with pytest.raises(ContractError):
        build_zones([{"trade_id": "run:fixed:000001", "competing": []}])


def test_build_zones_keeps_competing_zones():
    dataset = build_zones([_zone_entry()])
    assert dataset.kind == "zones"
    assert dataset.record_count == 1
    assert dataset.payload["trades"][0]["selected"]["zone_id"] == 39
    assert dataset.payload["trades"][0]["competing"] == []


def test_build_zones_rejects_an_inverted_zone():
    """upper below lower is a geometry bug, not a renderable zone."""

    entry = _zone_entry()
    entry["selected"]["upper"] = 400.0
    with pytest.raises(ContractError):
        build_zones([entry])


def _bar(timestamp, low=99.0, high=101.0):
    return {"timestamp": timestamp, "open": 100.0, "high": high, "low": low, "close": 100.5, "volume": 10.0}


def _window_entry(trade_id="run:fixed:000001"):
    return {
        "trade_id": trade_id,
        "one_hour": [_bar("2021-08-03T13:00:00Z"), _bar("2021-08-03T14:00:00Z")],
        "fifteen_minute": [_bar("2021-08-03T14:15:00Z")],
    }


def test_build_audit_windows_spans_every_bar_it_carries():
    dataset = build_audit_windows([_window_entry()])
    assert dataset.kind == "candles"
    assert dataset.dataset_id == "audit_windows"
    assert dataset.record_count == 1
    assert dataset.first_timestamp == "2021-08-03T13:00:00Z"
    assert dataset.last_timestamp == "2021-08-03T14:15:00Z"


def test_build_audit_windows_rejects_an_impossible_bar():
    """low above high is not a bar; rendering it would draw an inverted candle."""

    entry = _window_entry()
    entry["one_hour"][0]["low"] = 500.0
    with pytest.raises(ContractError):
        build_audit_windows([entry])


def test_build_audit_windows_rejects_unordered_bars():
    entry = _window_entry()
    entry["one_hour"] = [_bar("2021-08-03T14:00:00Z"), _bar("2021-08-03T13:00:00Z")]
    with pytest.raises(ContractError):
        build_audit_windows([entry])


def test_build_audit_windows_rejects_a_trade_with_no_bars():
    with pytest.raises(ContractError):
        build_audit_windows([{"trade_id": "run:fixed:000001", "one_hour": [], "fifteen_minute": []}])


# --- run_summary: the run metadata the dashboard used to hardcode ---


def _report():
    return {
        "candidate_signal_count": 93,
        "session_eligible_signal_count": 39,
        "backtest_configuration": {
            "starting_equity": 100000.0,
            "slippage_bps_per_side": 1.0,
            "commission_per_share_per_side": 0.005,
        },
        "data": {
            "one_hour_bar_count": 9189,
            "fifteen_minute_bar_count": 34200,
            "fifteen_minute_first": "2021-04-14T13:30:00Z",
            "fifteen_minute_last": "2026-07-16T19:45:00Z",
        },
        "results": {"fixed": {"details": {"trades": 38, "total_costs": 41.83}}},
    }


def test_run_summary_carries_signal_counts_and_starting_equity():
    dataset = build_run_summary(_report())
    assert dataset.kind == "run_summary"
    assert dataset.dataset_id == "run_summary"
    assert dataset.payload["signals"] == {"candidate": 93, "eligible": 39}
    assert dataset.payload["starting_equity"] == 100000.0


def test_run_summary_records_the_cost_model_when_present():
    payload = build_run_summary(_report()).payload
    assert payload["cost_model"] == {
        "recorded": True,
        "slippage_bps_per_side": 1.0,
        "commission_per_share_per_side": 0.005,
    }


def test_run_summary_marks_an_unrecorded_cost_model_rather_than_inventing_one():
    """Most runs predate backtest_configuration. Reporting a default here
    would let the comparison screen claim two runs share a cost model when
    one of them never stated any.
    """

    report = _report()
    del report["backtest_configuration"]
    payload = build_run_summary(report).payload
    assert payload["cost_model"]["recorded"] is False
    assert payload["cost_model"]["slippage_bps_per_side"] is None
    assert payload["starting_equity"] is None


def test_run_summary_keeps_per_variant_details():
    payload = build_run_summary(_report()).payload
    assert payload["variants"]["fixed"]["total_costs"] == 41.83


def test_run_summary_tolerates_a_report_with_nothing_useful():
    payload = build_run_summary({}).payload
    assert payload["signals"] == {"candidate": None, "eligible": None}
    assert payload["variants"] == {}
    assert payload["data"]["setup_bar_count"] is None
