import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_audit_datasets import (
    _auditable_report,
    _uses_default_indicator_parameters,
    audit_datasets_for,
    load_signals,
    load_trades,
    max_long_penetration_for,
    report_bar_paths,
    resolve_max_long_penetration,
    window,
)
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters

REPO_ROOT = Path(__file__).resolve().parent.parent
S4_RESULT = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"
RESULTS = S4_RESULT


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

# --- helpers moved here from test_build_strategy_04_fixture.py ---
#
# These cover real bugs already found: a v1 signals CSV that has no
# penetration column at all, and a forgotten CLI flag that silently turned
# the v1.1 penetration rule into an unconditional pass. The generator they
# were written against is gone; the functions they cover moved into this
# module, so the tests move with them unchanged.


def _bars() -> list[OHLCVBar]:
    return [
        OHLCVBar("2021-08-03T14:%02d:00Z" % minute, 1.0, 2.0, 0.5, 1.5, 10.0)
        for minute in range(0, 60, 15)
    ]


def test_window_clips_at_the_start_of_the_series():
    selected = window(_bars(), "2021-08-03T14:00:00Z", "2021-08-03T14:15:00Z", 5, 1)
    assert [bar.timestamp for bar in selected] == [
        "2021-08-03T14:00:00Z",
        "2021-08-03T14:15:00Z",
        "2021-08-03T14:30:00Z",
    ]


def test_window_clips_at_the_end_of_the_series():
    selected = window(_bars(), "2021-08-03T14:30:00Z", "2021-08-03T14:45:00Z", 1, 5)
    assert [bar.timestamp for bar in selected] == [
        "2021-08-03T14:15:00Z",
        "2021-08-03T14:30:00Z",
        "2021-08-03T14:45:00Z",
    ]


def test_signals_and_trades_join_on_decision_timestamp():
    signals = load_signals(RESULTS / "candidate_signals.csv")
    trades = load_trades(RESULTS / "fixed_trades.csv")
    signal_keys = {signal.decision_timestamp for signal in signals}
    assert {trade.decision_timestamp for trade in trades} <= signal_keys


def test_load_signals_tolerates_a_missing_penetration_column(tmp_path):
    """v1's candidate_signals.csv predates the penetration rule and has no

    long_zone_penetration_fraction column at all. load_signals must not raise
    KeyError for it -- the column's absence should just read as None.
    """
    csv_path = tmp_path / "candidate_signals.csv"
    csv_path.write_text(
        "decision_timestamp,entry_timestamp,side,zone_id,zone_side,zone_lower,"
        "zone_upper,trigger_timestamp,trigger_low,one_hour_atr,"
        "one_hour_atr_timestamp,stop_buffer,reward_to_risk\n"
        "2021-08-03T14:30:00Z,2021-08-03T14:30:00Z,long,39,demand,437.0,437.9,"
        "2021-08-03T14:15:00Z,437.5,1.0,2021-08-03T14:00:00Z,0.05,1.0\n",
        encoding="utf-8",
    )
    signals = load_signals(csv_path)
    assert len(signals) == 1
    assert signals[0].long_zone_penetration_fraction is None


def test_load_signals_reads_a_present_penetration_column(tmp_path):
    """v1.1's column is still read normally when it is present."""

    csv_path = tmp_path / "candidate_signals.csv"
    csv_path.write_text(
        "decision_timestamp,entry_timestamp,side,zone_id,zone_side,zone_lower,"
        "zone_upper,trigger_timestamp,trigger_low,one_hour_atr,"
        "one_hour_atr_timestamp,stop_buffer,long_zone_penetration_fraction,"
        "reward_to_risk\n"
        "2021-08-03T14:30:00Z,2021-08-03T14:30:00Z,long,39,demand,437.0,437.9,"
        "2021-08-03T14:15:00Z,437.5,1.0,2021-08-03T14:00:00Z,0.05,0.2,1.0\n",
        encoding="utf-8",
    )
    signals = load_signals(csv_path)
    assert signals[0].long_zone_penetration_fraction == 0.2


# --- the penetration cap belongs to the strategy version, not to the CLI ---
#
# --max-long-penetration used to default to None, and None means "this
# version has no penetration rule at all". So forgetting the flag while
# auditing v1.1 did not produce an error or even a warning: it silently
# turned a real rule into an unconditional pass for every long trade.


def test_each_known_version_declares_its_own_penetration_cap():
    assert max_long_penetration_for("v1") is None
    assert max_long_penetration_for("v1_1") == 0.25
    assert max_long_penetration_for("v1_2") == 0.25


def test_an_unknown_version_fails_loudly_rather_than_disabling_the_rule():
    with pytest.raises(ValueError):
        max_long_penetration_for("v9_9")


def test_omitting_the_flag_derives_the_cap_from_the_version():
    assert resolve_max_long_penetration(None, "v1") is None
    assert resolve_max_long_penetration(None, "v1_1") == 0.25
    assert resolve_max_long_penetration(None, "v1_2") == 0.25


def test_a_forgotten_flag_no_longer_disables_the_v1_1_rule():
    assert resolve_max_long_penetration(None, "v1_1") is not None


def test_an_explicit_flag_still_overrides_the_version_default():
    assert resolve_max_long_penetration("0.4", "v1_1") == 0.4
    assert resolve_max_long_penetration("none", "v1_1") is None
    assert resolve_max_long_penetration("NONE", "v1_1") is None


def test_an_unknown_version_with_an_explicit_flag_is_accepted():
    """Only the silent default is dangerous; a stated value is evidence."""

    assert resolve_max_long_penetration("0.25", "v9_9") == 0.25


# --- signal audit skips runs whose recorded indicator parameters are not
# the v0.3 defaults, instead of rebuilding the zone timeline with the wrong
# parameters and either raising ContractError or (worse) silently matching
# a wrong zone by id. See docs/superpowers/sdd/final-fixes-report.md finding 1.


def _default_indicator_parameters() -> dict:
    return json.loads(json.dumps(asdict(strategy_04_v0_3_parameters())))


def _fx_indicator_parameters() -> dict:
    return json.loads(
        json.dumps(
            asdict(
                replace(
                    strategy_04_v0_3_parameters(),
                    profile_weighting="time",
                    session_day_boundary="fx_17et",
                )
            )
        )
    )


def test_uses_default_indicator_parameters_is_true_for_the_default_report():
    report = {"indicator_parameters": _default_indicator_parameters()}
    assert _uses_default_indicator_parameters(report) is True


def test_uses_default_indicator_parameters_is_false_for_fx_parameters():
    report = {"indicator_parameters": _fx_indicator_parameters()}
    assert _uses_default_indicator_parameters(report) is False


def test_uses_default_indicator_parameters_treats_a_missing_field_as_default():
    """Old reports predate profile_weighting/session_day_boundary entirely;
    their absence describes the same behaviour the current defaults do, not
    a mismatch."""

    params = _default_indicator_parameters()
    del params["profile_weighting"]
    del params["session_day_boundary"]
    report = {"indicator_parameters": params}
    assert _uses_default_indicator_parameters(report) is True


def test_uses_default_indicator_parameters_treats_a_missing_block_as_default():
    assert _uses_default_indicator_parameters({}) is True


def _write_minimal_strategy_04_report(result_dir: Path, indicator_parameters: dict) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "strategy_id": "strategy_04_v1_1_shallow_long_penetration",
        "indicator_parameters": indicator_parameters,
        "data": {
            "one_hour_file": "does/not/exist_1h.csv",
            "fifteen_minute_file": "does/not/exist_15m.csv",
        },
    }
    (result_dir / "backtest_report.json").write_text(json.dumps(report), encoding="utf-8")
    (result_dir / "candidate_signals.csv").write_text("", encoding="utf-8")
    (result_dir / "fixed_trades.csv").write_text("", encoding="utf-8")


def test_auditable_report_is_none_when_indicator_parameters_are_not_default(tmp_path):
    _write_minimal_strategy_04_report(tmp_path, _fx_indicator_parameters())
    assert _auditable_report(tmp_path) is None


def test_auditable_report_is_kept_when_indicator_parameters_are_default(tmp_path):
    _write_minimal_strategy_04_report(tmp_path, _default_indicator_parameters())
    assert _auditable_report(tmp_path) is not None


def test_audit_datasets_for_skips_without_raising_when_parameters_do_not_match(tmp_path):
    """This is the honest-skip path: a run whose recorded indicator
    parameters differ from the v0.3 defaults must not raise ContractError
    and must not be audited against the wrong zone geometry.
    """

    _write_minimal_strategy_04_report(tmp_path, _fx_indicator_parameters())
    assert audit_datasets_for(tmp_path, REPO_ROOT) == []


def test_audit_datasets_for_the_real_fx_run_does_not_raise():
    """Reproduces finding 1: before the fix, this raised ContractError
    because the rebuilt zone timeline used the wrong indicator parameters.
    """

    fx_dir = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "eurusd_1h_15m"
    if not fx_dir.is_dir():
        pytest.skip("FX baseline results not present in this checkout")
    assert audit_datasets_for(fx_dir, REPO_ROOT) == []
