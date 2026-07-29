import json
import sys
from datetime import datetime, timedelta, timezone

from ai_trade.backtest_strategy_04_v1_1_fx import main
from ai_trade.market_data import OHLCVBar, save_bars


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_fixture(directory) -> tuple[str, str]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    hours = [
        OHLCVBar(_stamp(start + timedelta(hours=i)),
                 1.10 + (i % 7) * 0.001, 1.102 + (i % 7) * 0.001,
                 1.098 + (i % 7) * 0.001, 1.101 + (i % 7) * 0.001, 0.0)
        for i in range(120)
    ]
    fifteen = [
        OHLCVBar(_stamp(start + timedelta(minutes=15 * i)),
                 1.10 + (i % 11) * 0.0004, 1.1015 + (i % 11) * 0.0004,
                 1.0985 + (i % 11) * 0.0004, 1.1005 + (i % 11) * 0.0004, 0.0)
        for i in range(480)
    ]
    save_bars(hours, directory=directory, symbol="EURUSD", timeframe="1h",
              source="test", extra={"volume": "none (midpoint data)"})
    save_bars(fifteen, directory=directory, symbol="EURUSD", timeframe="15m",
              source="test", extra={"volume": "none (midpoint data)"})
    return str(directory / "eurusd_15m.csv"), str(directory / "eurusd_1h.csv")


def test_fx_runner_writes_contract_files(tmp_path, monkeypatch):
    fifteen, hours = _write_fixture(tmp_path / "cache")
    output = tmp_path / "results"
    monkeypatch.setattr(sys, "argv", [
        "backtest_strategy_04_v1_1_fx", "--pair", "EURUSD",
        "--fifteen-minute", fifteen, "--one-hour", hours,
        "--output", str(output), "--skip-publish",
    ])
    assert main() == 0
    for name in ("candidate_signals.csv", "fixed_trades.csv", "fixed_summary.json",
                 "rrms_trades.csv", "rrms_summary.json", "backtest_report.json"):
        assert (output / name).is_file(), name

    report = json.loads((output / "backtest_report.json").read_text(encoding="utf-8"))
    assert report["strategy_id"] == "strategy_04_v1_1_shallow_long_penetration"
    assert report["symbol"] == "EURUSD"
    assert report["market"] == "spot_fx_midpoint"
    assert report["indicator_parameters"]["profile_weighting"] == "time"
    assert report["indicator_parameters"]["session_day_boundary"] == "fx_17et"
    assert report["backtest_configuration"]["commission_bps_per_side"] == 0.20
    assert "TPO" in report["warning"]
