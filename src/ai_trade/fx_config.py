"""Research-only spot-FX backtest configuration presets.

The FX week runs Sunday 17:00 to Friday 17:00 New York time. Entries are
blocked in the 17:00-18:00 rollover hour (thin books, wide spreads, broker
maintenance) via the midnight-spanning entry window 18:00 -> 17:00. Friday
entries stay blocked and positions go flat by Friday 16:45, before the
17:00 close. Commission follows IBKR IDEALPRO tier 1 (0.20 bps of notional
per side, $2.00 per-order minimum); the half-spread of midpoint fills is
folded into ``slippage_bps_per_side`` per pair. All values are parameters
for the existing cost-stress workflow, not validated constants.
"""

from __future__ import annotations

from ai_trade.backtest_strategy_01 import BacktestConfig

FX_HALF_SPREAD_BPS = {"EURUSD": 0.5, "GBPUSD": 0.7}


def fx_backtest_config(pair: str) -> BacktestConfig:
    """Return the 24/5 spot-FX preset for one supported pair."""
    return BacktestConfig(
        slippage_bps_per_side=FX_HALF_SPREAD_BPS[pair.upper()],
        block_friday_entries=True,
        force_friday_close=True,
        friday_close_time=(16, 45),
        entry_window_start=(18, 0),
        entry_window_end=(17, 0),
        commission_bps_per_side=0.20,
        min_commission_per_order=2.0,
    )
