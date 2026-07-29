import pytest

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest
from ai_trade.fx_config import FX_HALF_SPREAD_BPS, fx_backtest_config
from ai_trade.market_data import OHLCVBar


def _fx_bars() -> list[OHLCVBar]:
    # Monday 2026-07-27, 23:00 UTC = 19:00 EDT (inside the FX entry window).
    return [
        OHLCVBar("2026-07-27T23:00:00Z", 1.10000, 1.10050, 1.09990, 1.10020, 0.0),
        OHLCVBar("2026-07-27T23:15:00Z", 1.10020, 1.10500, 1.10010, 1.10400, 0.0),
    ]


def _signal(entry_timestamp: str) -> dict[str, object]:
    return {
        "decision_timestamp": entry_timestamp,
        "entry_timestamp": entry_timestamp,
        "side": "long",
        "jaw": 1.09800,
        "stop_reference": 1.09800,
    }


def test_fx_preset_values():
    config = fx_backtest_config("EURUSD")
    assert config.commission_bps_per_side == 0.20
    assert config.min_commission_per_order == 2.0
    assert config.slippage_bps_per_side == FX_HALF_SPREAD_BPS["EURUSD"] == 0.5
    assert fx_backtest_config("gbpusd").slippage_bps_per_side == 0.7
    assert config.block_friday_entries is True
    assert config.friday_close_time == (16, 45)
    assert config.entry_window_start == (18, 0)
    assert config.entry_window_end == (17, 0)


def test_bps_commission_with_binding_minimum():
    config = fx_backtest_config("EURUSD")
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    assert len(trades) == 1
    trade = trades[0]
    # ~75k units at ~1.10: 0.20 bps per side is ~$1.65 < $2 minimum, so
    # the $2 per-order minimum binds on both sides.
    per_side_entry = trade.entry_price * trade.quantity * 0.20 / 10_000
    assert per_side_entry < 2.0
    assert trade.costs == pytest.approx(4.0)


def test_bps_commission_without_minimum():
    config = BacktestConfig(
        commission_bps_per_side=0.20, min_commission_per_order=0.0,
        slippage_bps_per_side=0.5, entry_window_start=(18, 0), entry_window_end=(17, 0),
    )
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    trade = trades[0]
    expected = (trade.entry_price + trade.exit_price) * trade.quantity * 0.20 / 10_000
    assert trade.costs == pytest.approx(expected)


def test_per_share_commission_still_default():
    config = BacktestConfig(entry_window_start=(18, 0), entry_window_end=(17, 0))
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    trade = trades[0]
    assert trade.costs == pytest.approx(trade.quantity * 0.005 * 2)


def test_rollover_hour_entries_are_blocked():
    config = fx_backtest_config("EURUSD")
    # 21:15 UTC = 17:15 EDT: inside the blocked 17:00-18:00 rollover hour.
    bars = [
        OHLCVBar("2026-07-27T21:15:00Z", 1.10000, 1.10050, 1.09990, 1.10020, 0.0),
        OHLCVBar("2026-07-27T21:30:00Z", 1.10020, 1.10500, 1.10010, 1.10400, 0.0),
    ]
    assert run_backtest(bars, [_signal("2026-07-27T21:15:00Z")], "fixed", config) == []
