from ai_trade.backtest_strategy_01 import BacktestConfig, _entry_allowed, run_backtest
from ai_trade.market_data import OHLCVBar


def make_bar(timestamp: str, open_: float, high: float, low: float, close: float) -> OHLCVBar:
    return OHLCVBar(timestamp=timestamp, open=open_, high=high, low=low, close=close, volume=1000)


def test_stop_wins_when_stop_and_target_are_both_touched_in_one_bar() -> None:
    bars = [make_bar("2026-01-05T15:45:00Z", 100, 102, 98, 100)]
    signals = [{"decision_timestamp": "2026-01-05T15:45:00Z", "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99}]

    trades = run_backtest(bars, signals, "fixed", BacktestConfig(slippage_bps_per_side=0, commission_per_share_per_side=0))

    assert trades[0].exit_reason == "stop"
    assert trades[0].exit_price == 99


def test_open_trade_is_force_closed_in_final_friday_bar() -> None:
    bars = [make_bar("2026-01-02T20:45:00Z", 100, 100.5, 99.5, 100.25)]  # 15:45 New York in winter.
    signals = [{"decision_timestamp": "2026-01-02T20:45:00Z", "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99}]

    trades = run_backtest(bars, signals, "fixed", BacktestConfig(slippage_bps_per_side=0, commission_per_share_per_side=0))

    assert trades[0].exit_reason == "weekend_close"
    assert trades[0].exit_price == 100.25


def test_v2_accepts_only_long_entries_before_the_final_hour_and_not_on_friday() -> None:
    config = BacktestConfig(
        slippage_bps_per_side=0,
        commission_per_share_per_side=0,
        allowed_direction="long",
        block_final_hour_entries=True,
        block_friday_entries=True,
    )
    bars = [
        make_bar("2026-01-08T19:45:00Z", 100, 101, 99, 100),  # Thursday 14:45 ET: allowed long entry, exits this bar.
        make_bar("2026-01-08T20:00:00Z", 100, 100.5, 99.5, 100),
        make_bar("2026-01-08T20:15:00Z", 100, 100.5, 99.5, 100),  # Thursday 15:15 ET: final hour.
        make_bar("2026-01-09T15:00:00Z", 100, 100.5, 99.5, 100),  # Friday 10:00 ET.
    ]
    signals = [
        {"decision_timestamp": bars[0].timestamp, "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99},
        {"decision_timestamp": bars[1].timestamp, "entry_timestamp": bars[1].timestamp, "side": "short", "jaw": 101},
        {"decision_timestamp": bars[2].timestamp, "entry_timestamp": bars[2].timestamp, "side": "long", "jaw": 99},
        {"decision_timestamp": bars[3].timestamp, "entry_timestamp": bars[3].timestamp, "side": "long", "jaw": 99},
    ]

    trades = run_backtest(bars, signals, "fixed", config)

    assert len(trades) == 1
    assert trades[0].side == "long"
    assert trades[0].entry_timestamp == "2026-01-08T19:45:00Z"


def test_hourly_trade_is_force_closed_by_the_final_friday_hourly_bar() -> None:
    bars = [make_bar("2026-01-02T20:30:00Z", 100, 100.5, 99.5, 100.25)]  # Friday 15:30 ET in winter.
    signals = [{"decision_timestamp": bars[0].timestamp, "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99}]
    config = BacktestConfig(slippage_bps_per_side=0, commission_per_share_per_side=0, entry_interval_minutes=60)

    trades = run_backtest(bars, signals, "fixed", config)

    assert trades[0].exit_reason == "weekend_close"
    assert trades[0].exit_price == 100.25


def test_weekend_variant_does_not_force_close_on_friday() -> None:
    bars = [make_bar("2026-01-02T20:30:00Z", 100, 100.5, 99.5, 100.25)]
    signals = [{"decision_timestamp": bars[0].timestamp, "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99}]
    config = BacktestConfig(
        slippage_bps_per_side=0,
        commission_per_share_per_side=0,
        entry_interval_minutes=60,
        force_friday_close=False,
    )

    assert run_backtest(bars, signals, "fixed", config) == []


def test_contract_multiplier_uses_whole_contract_risk_and_pnl() -> None:
    bars = [make_bar("2026-01-05T15:45:00Z", 100, 101, 99, 100)]
    signals = [{"decision_timestamp": bars[0].timestamp, "entry_timestamp": bars[0].timestamp, "side": "long", "jaw": 99}]
    config = BacktestConfig(
        starting_equity=10_000,
        fixed_risk_percent=0.0015,
        slippage_bps_per_side=0,
        commission_per_contract_per_side=0,
        contract_multiplier=10,
    )

    trades = run_backtest(bars, signals, "fixed", config)

    assert trades[0].quantity == 1  # $15 risk budget / ($1 * 10) risk per MGC contract.
    assert trades[0].gross_pnl == -10  # Conservative same-bar collision selects the $1 stop first.


def test_mgc_globex_entry_window_excludes_first_and_last_session_hours() -> None:
    config = BacktestConfig(entry_window_start=(19, 0), entry_window_end=(16, 0), block_friday_entries=True)

    assert not _entry_allowed("2026-01-05T23:00:00Z", "long", config)  # Monday 18:00 ET.
    assert _entry_allowed("2026-01-06T00:00:00Z", "long", config)  # Monday 19:00 ET.
    assert not _entry_allowed("2026-01-06T21:00:00Z", "long", config)  # Tuesday 16:00 ET.


def test_rrms_can_reset_after_its_maximum_tier() -> None:
    bars = [make_bar(f"2026-01-0{day}T15:45:00Z", 100, 101, 90, 95) for day in range(1, 7)]
    signals = [
        {"decision_timestamp": bar.timestamp, "entry_timestamp": bar.timestamp, "side": "long", "jaw": 99}
        for bar in bars[:5]
    ]
    trades = run_backtest(
        bars,
        signals,
        "rrms",
        BacktestConfig(rrms_reset_after_max_tier=True, entry_interval_minutes=15),
    )
    assert len(trades) == 5
    assert [trade.rrms_tier for trade in trades] == [0, 1, 2, 3, 0]
