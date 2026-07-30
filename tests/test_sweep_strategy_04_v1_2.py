from datetime import datetime, timedelta, timezone

from ai_trade.backtest_strategy_01 import BacktestConfig
from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters
from ai_trade.sweep_strategy_04_v1_2_risk_ratio import sweep_symbol


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bars(count: int, minutes: int) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return [
        OHLCVBar(_stamp(start + timedelta(minutes=minutes * i)),
                 100 + (i % 7) * 0.15, 100.5 + (i % 7) * 0.15,
                 99.7 + (i % 7) * 0.15, 100.25 + (i % 7) * 0.15, 1000.0)
        for i in range(count)
    ]


def test_sweep_rows_shape_and_unfiltered_limit():
    hours = _bars(200, 60)
    fifteen = _bars(800, 15)
    rows = sweep_symbol(
        fifteen, hours, strategy_04_v0_3_parameters(), BacktestConfig(),
        thresholds=(1.0, 2.0, 1000.0),
    )
    assert [row["threshold"] for row in rows] == [1.0, 2.0, 1000.0]
    # NOTE: signal counts are NOT asserted monotonic in threshold on purpose:
    # rejecting a reaction leaves its zone unconsumed, which can create MORE
    # later signals at a tighter threshold. The only guaranteed anchor is
    # that an effectively infinite threshold rejects nothing.
    for row in rows:
        for key in ("threshold", "candidate_signal_count", "rejected_vs_unfiltered",
                    "trade_count", "win_rate", "average_r", "net_pnl"):
            assert key in row
    assert rows[-1]["rejected_vs_unfiltered"] == 0
