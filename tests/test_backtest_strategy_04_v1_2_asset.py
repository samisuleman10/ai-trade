import json
import sys
from datetime import datetime, timedelta, timezone

from ai_trade.backtest_strategy_04_v1_2_asset import VARIANTS, main, symbol_run_inputs
from ai_trade.market_data import OHLCVBar, save_bars


def test_variant_flag_mapping():
    assert VARIANTS == {
        "base": (False, False),
        "a": (True, False),
        "b": (False, True),
        "ab": (True, True),
    }


def test_symbol_run_inputs_dispatches_equity_vs_fx():
    _, _, config, indicator, market = symbol_run_inputs("SPY")
    assert market == "equity"
    assert config.commission_bps_per_side is None
    assert indicator.profile_weighting == "volume"
    assert indicator.session_day_boundary == "calendar"

    fifteen, hours, config, indicator, market = symbol_run_inputs("EURUSD")
    assert market == "spot_fx_midpoint"
    assert config.commission_bps_per_side == 0.20
    assert indicator.profile_weighting == "time"
    assert indicator.session_day_boundary == "fx_17et"
    assert "EURUSD" in str(fifteen)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_fixture(directory) -> tuple[str, str]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    hours = [
        OHLCVBar(_stamp(start + timedelta(hours=i)), 100 + (i % 5) * 0.2,
                 100.6 + (i % 5) * 0.2, 99.8 + (i % 5) * 0.2, 100.3 + (i % 5) * 0.2, 1000.0)
        for i in range(120)
    ]
    fifteen = [
        OHLCVBar(_stamp(start + timedelta(minutes=15 * i)), 100 + (i % 9) * 0.1,
                 100.4 + (i % 9) * 0.1, 99.9 + (i % 9) * 0.1, 100.2 + (i % 9) * 0.1, 1000.0)
        for i in range(480)
    ]
    save_bars(hours, directory=directory, symbol="SPY", timeframe="1h", source="test")
    save_bars(fifteen, directory=directory, symbol="SPY", timeframe="15m", source="test")
    return str(directory / "spy_15m.csv"), str(directory / "spy_1h.csv")


def test_runner_writes_contract_files_and_variant_metadata(tmp_path, monkeypatch):
    fifteen, hours = _write_fixture(tmp_path / "cache")
    output = tmp_path / "results"
    monkeypatch.setattr(sys, "argv", [
        "backtest_strategy_04_v1_2_asset", "--symbol", "SPY", "--variant", "ab",
        "--fifteen-minute", fifteen, "--one-hour", hours,
        "--output", str(output), "--skip-publish",
    ])
    assert main() == 0
    for name in ("candidate_signals.csv", "fixed_trades.csv", "fixed_summary.json",
                 "rrms_trades.csv", "rrms_summary.json", "backtest_report.json"):
        assert (output / name).is_file(), name
    report = json.loads((output / "backtest_report.json").read_text(encoding="utf-8"))
    assert report["strategy_id"] == "strategy_04_v1_2_rejection_filters"
    assert report["variant"] == "ab"
    assert report["execution_parameters"]["enable_filter_a"] is True
    assert report["execution_parameters"]["enable_filter_b"] is True
    assert report["execution_parameters"]["max_risk_zone_ratio"] == 2.5
    assert "not been validated" in report["warning"]
