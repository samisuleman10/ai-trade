"""RRMS simulator with a capped five-loss cycle and no weekly reset."""

from __future__ import annotations

from typing import Iterable

from ai_trade.backtest_strategy_01 import BacktestConfig, Trade, _entry_allowed, _exit_trade, _fill, trade_costs
from ai_trade.market_data import OHLCVBar


FIVE_LOSS_TIERS = (0.0015, 0.0035, 0.0070, 0.0150, 0.0150)


def run_backtest_five_loss_reset(
    entry_bars: Iterable[OHLCVBar],
    signals: Iterable[dict[str, object]],
    config: BacktestConfig,
) -> list[Trade]:
    """Increase after every negative exit and reset after profit or loss five.

    The sequence carries across trading weeks. Any negative net P&L—including
    a Friday forced close—counts as a loss. The fifth consecutive loss uses the
    capped 1.50% tier, then the next trade restarts at 0.15%.
    """
    bars = list(entry_bars)
    by_timestamp = {bar.timestamp: index for index, bar in enumerate(bars)}
    equity = config.starting_equity
    loss_count = 0
    next_free_index = 0
    trades: list[Trade] = []

    for signal in signals:
        entry_index = by_timestamp.get(str(signal["entry_timestamp"]))
        if entry_index is None or entry_index < next_free_index:
            continue
        side = str(signal["side"])
        if not _entry_allowed(bars[entry_index].timestamp, side, config):
            continue
        raw_entry = bars[entry_index].open
        entry = _fill(raw_entry, side, "entry", config.slippage_bps_per_side)
        stop = float(signal.get("stop_reference", signal["jaw"]))
        price_risk = entry - stop if side == "long" else stop - entry
        risk_per_unit = price_risk * config.contract_multiplier
        if risk_per_unit <= 0:
            continue
        target = entry + price_risk if side == "long" else entry - price_risk
        tier = min(loss_count, len(FIVE_LOSS_TIERS) - 1)
        risk_dollars = equity * FIVE_LOSS_TIERS[tier]
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
            exit_timestamp=bars[exit_index].timestamp, side=side, rrms_tier=tier,
            quantity=quantity, entry_price=entry, stop_price=stop, target_price=target,
            exit_price=exit_price, exit_reason=exit_reason, gross_pnl=gross_pnl,
            costs=costs, net_pnl=net_pnl, result_r=result_r, equity_after=equity,
        ))
        next_free_index = exit_index + 1

        if net_pnl > 0:
            loss_count = 0
        elif net_pnl < 0:
            loss_count += 1
            if loss_count >= len(FIVE_LOSS_TIERS):
                loss_count = 0
    return trades
