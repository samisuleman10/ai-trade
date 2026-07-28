from ai_trade.backtest_strategy_01 import BacktestConfig
from ai_trade.market_data import OHLCVBar
from ai_trade.rrms_four_loss_reset import FOUR_LOSS_TIERS, run_backtest_four_loss_reset


def _bar(timestamp: str) -> OHLCVBar:
    return OHLCVBar(timestamp, 100.0, 101.0, 98.0, 99.0, 1.0)


def test_fourth_loss_uses_final_tier_then_next_trade_resets(monkeypatch):
    bars = [
        _bar("2026-07-06T15:30:00Z"),
        _bar("2026-07-07T15:30:00Z"),
        _bar("2026-07-08T15:30:00Z"),
        _bar("2026-07-09T15:30:00Z"),
        _bar("2026-07-13T15:30:00Z"),
    ]
    signals = [
        {
            "decision_timestamp": bar.timestamp,
            "entry_timestamp": bar.timestamp,
            "side": "long",
            "jaw": 99.0,
            "stop_reference": 99.0,
        }
        for bar in bars
    ]

    def always_negative(rows, start_index, side, entry, stop, target, config):
        return start_index, stop, "stop"

    monkeypatch.setattr("ai_trade.rrms_four_loss_reset._exit_trade", always_negative)
    trades = run_backtest_four_loss_reset(
        bars,
        signals,
        BacktestConfig(
            entry_interval_minutes=60,
            force_friday_close=False,
            slippage_bps_per_side=0,
            commission_per_share_per_side=0,
        ),
    )

    assert FOUR_LOSS_TIERS == (0.0015, 0.0035, 0.0070, 0.0150)
    assert [trade.rrms_tier for trade in trades] == [0, 1, 2, 3, 0]
