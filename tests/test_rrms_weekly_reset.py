from ai_trade.backtest_strategy_01 import BacktestConfig
from ai_trade.market_data import OHLCVBar
from ai_trade.rrms_weekly_reset import run_backtest_weekly_reset


def _bar(timestamp: str) -> OHLCVBar:
    return OHLCVBar(timestamp=timestamp, open=100.0, high=101.0, low=98.0, close=99.0, volume=1.0)


def test_new_week_resets_rrms_tier(monkeypatch):
    bars = [
        _bar("2026-07-06T15:30:00Z"),
        _bar("2026-07-07T15:30:00Z"),
        _bar("2026-07-13T15:30:00Z"),
    ]
    signals = [
        {"decision_timestamp": bar.timestamp, "entry_timestamp": bar.timestamp, "side": "long", "jaw": 99.0, "stop_reference": 99.0}
        for bar in bars
    ]

    def always_stop(rows, start_index, side, entry, stop, target, config):
        return start_index, stop, "stop"

    monkeypatch.setattr("ai_trade.rrms_weekly_reset._exit_trade", always_stop)
    trades = run_backtest_weekly_reset(
        bars, signals,
        BacktestConfig(entry_interval_minutes=60, force_friday_close=False, slippage_bps_per_side=0, commission_per_share_per_side=0),
    )
    assert [trade.rrms_tier for trade in trades] == [0, 1, 0]
