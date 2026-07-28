import json
from pathlib import Path

from ai_trade.build_strategy_04_fixture import (
    load_signals,
    load_trades,
    window,
)
from ai_trade.market_data import OHLCVBar

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"
FIXTURE = REPO_ROOT / "dashboard" / "src" / "fixtures" / "strategy_04_v1_1_spy.json"


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


def test_fixture_reconciles_with_the_backtest_report():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = json.loads((RESULTS / "fixed_summary.json").read_text(encoding="utf-8"))
    assert len(fixture["trades"]) == summary["trade_count"]
    assert abs(fixture["summary"]["net_pnl"] - summary["net_pnl"]) < 1e-6
    assert abs(fixture["summary"]["ending_equity"] - summary["ending_equity"]) < 1e-6


def test_every_trade_carries_zones_and_bar_windows():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for trade in fixture["trades"]:
        assert trade["zones"]["selected"]["zone_id"] > 0
        assert len(trade["bars"]["one_hour"]) > 0
        assert len(trade["bars"]["fifteen_minute"]) > 0
        assert len(trade["audit"]["checks"]) == 10
