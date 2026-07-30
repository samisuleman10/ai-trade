"""RRMS simulator that always starts each trading week at the base tier."""

from __future__ import annotations

from typing import Iterable
from zoneinfo import ZoneInfo

from ai_trade.backtest_strategy_01 import (
    BacktestConfig,
    RRMS_TIERS,
    Trade,
    _entry_allowed,
    _exit_trade,
    _fill,
    _timestamp,
    trade_costs,
)
from ai_trade.market_data import OHLCVBar


def run_backtest_weekly_reset(
    entry_bars: Iterable[OHLCVBar],
    signals: Iterable[dict[str, object]],
    config: BacktestConfig,
) -> list[Trade]:
    """Run RRMS, resetting tier/state on every new ISO trading week.

    A Friday forced close also resets immediately. A stop at tier 3 blocks new
    entries only for the remainder of that week; the next week starts at tier 0.
    """
    bars = list(entry_bars)
    by_timestamp = {bar.timestamp: index for index, bar in enumerate(bars)}
    equity = config.starting_equity
    rrms_tier = 0
    active_week: tuple[int, int] | None = None
    blocked_week: tuple[int, int] | None = None
    next_free_index = 0
    trades: list[Trade] = []
    timezone = ZoneInfo(config.session_timezone)

    for signal in signals:
        entry_index = by_timestamp.get(str(signal["entry_timestamp"]))
        if entry_index is None or entry_index < next_free_index:
            continue
        side = str(signal["side"])
        if not _entry_allowed(bars[entry_index].timestamp, side, config):
            continue
        local_entry = _timestamp(bars[entry_index].timestamp).astimezone(timezone)
        iso = local_entry.isocalendar()
        entry_week = (iso.year, iso.week)
        if active_week != entry_week:
            active_week = entry_week
            rrms_tier = 0
            blocked_week = None
        if blocked_week == entry_week:
            continue

        raw_entry = bars[entry_index].open
        entry = _fill(raw_entry, side, "entry", config.slippage_bps_per_side)
        stop = float(signal.get("stop_reference", signal["jaw"]))
        price_risk = entry - stop if side == "long" else stop - entry
        risk_per_unit = price_risk * config.contract_multiplier
        if risk_per_unit <= 0:
            continue
        target = entry + price_risk if side == "long" else entry - price_risk
        risk_dollars = equity * RRMS_TIERS[rrms_tier]
        quantity = int(risk_dollars // risk_per_unit)
        if quantity < 1:
            continue
        exit_result = _exit_trade(bars, entry_index, side, entry, stop, target, config)
        if exit_result is None:
            break
        exit_index, exit_price, exit_reason = exit_result
        direction = 1 if side == "long" else -1
        gross_pnl = quantity * (exit_price - entry) * direction * config.contract_multiplier
        costs = trade_costs(entry, exit_price, quantity, config)
        net_pnl = gross_pnl - costs
        planned_risk = quantity * risk_per_unit
        result_r = net_pnl / planned_risk
        equity += net_pnl
        trades.append(Trade(
            decision_timestamp=str(signal["decision_timestamp"]), entry_timestamp=bars[entry_index].timestamp,
            exit_timestamp=bars[exit_index].timestamp, side=side, rrms_tier=rrms_tier,
            quantity=quantity, entry_price=entry, stop_price=stop, target_price=target,
            exit_price=exit_price, exit_reason=exit_reason, gross_pnl=gross_pnl,
            costs=costs, net_pnl=net_pnl, result_r=result_r, equity_after=equity,
        ))
        next_free_index = exit_index + 1

        if exit_reason == "weekend_close":
            rrms_tier = 0
        elif exit_reason == "stop":
            if rrms_tier == len(RRMS_TIERS) - 1:
                blocked_week = entry_week
            else:
                rrms_tier += 1
        elif net_pnl > 0:
            rrms_tier = 0
    return trades
