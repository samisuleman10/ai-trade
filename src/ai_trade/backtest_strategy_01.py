"""Conservative bar-by-bar backtest for Strategy 01; it never submits orders."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Iterable, Literal
from zoneinfo import ZoneInfo

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import candidate_signals, candidate_signals_v4, candidate_signals_v5, load_ohlcv_csv


SizingMode = Literal["fixed", "rrms"]
DirectionFilter = Literal["both", "long", "short"]
EASTERN = ZoneInfo("America/New_York")
RRMS_TIERS = (0.0015, 0.0035, 0.0070, 0.0150)


@dataclass(frozen=True)
class BacktestConfig:
    starting_equity: float = 100_000.0
    fixed_risk_percent: float = 0.0015
    slippage_bps_per_side: float = 1.0
    commission_per_share_per_side: float = 0.005
    allowed_direction: DirectionFilter = "both"
    block_opening_hour_entries: bool = False
    block_final_hour_entries: bool = False
    block_friday_entries: bool = False
    entry_interval_minutes: int = 15
    force_friday_close: bool = True
    contract_multiplier: float = 1.0
    commission_per_contract_per_side: float | None = None
    commission_bps_per_side: float | None = None
    min_commission_per_order: float = 0.0
    session_timezone: str = "America/New_York"
    entry_window_start: tuple[int, int] | None = None
    entry_window_end: tuple[int, int] | None = None
    friday_close_time: tuple[int, int] = (16, 0)
    rrms_reset_after_max_tier: bool = False


@dataclass(frozen=True)
class Trade:
    decision_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    side: str
    rrms_tier: int
    quantity: int
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    gross_pnl: float
    costs: float
    net_pnl: float
    result_r: float
    equity_after: float


def _timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))


def _fill(price: float, side: str, action: Literal["entry", "stop", "target", "close"], slippage_bps: float) -> float:
    """Apply adverse slippage to every simulated fill."""
    fraction = slippage_bps / 10_000
    buying = (side == "long" and action == "entry") or (side == "short" and action != "entry")
    return price * (1 + fraction if buying else 1 - fraction)


def _is_friday_close(bar: OHLCVBar, config: BacktestConfig) -> bool:
    start = _timestamp(bar.timestamp).astimezone(ZoneInfo(config.session_timezone))
    if start.weekday() != 4:
        return False
    end = start + timedelta(minutes=config.entry_interval_minutes)
    hour, minute = config.friday_close_time
    friday_close = start.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return start <= friday_close <= end


def _within_window(value: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> bool:
    """Return whether a time is inside an inclusive-start, exclusive-end window.

    Windows such as 19:00–16:00 are allowed and intentionally span midnight.
    """
    if start < end:
        return start <= value < end
    return value >= start or value < end


def _entry_allowed(timestamp: str, side: str, config: BacktestConfig) -> bool:
    """Apply versioned trade filters to the executable next-bar entry time."""
    if config.allowed_direction != "both" and side != config.allowed_direction:
        return False
    local = _timestamp(timestamp).astimezone(ZoneInfo(config.session_timezone))
    local_time = (local.hour, local.minute)
    if config.entry_window_start is not None and config.entry_window_end is not None and not _within_window(
        local_time, config.entry_window_start, config.entry_window_end
    ):
        return False
    if config.block_opening_hour_entries and local_time < (10, 30):
        return False
    if config.block_friday_entries and local.weekday() == 4:
        return False
    # The final regular-session hour begins at 15:00 New York time. A setup
    # completing at 14:45 would enter at 14:45 and is still allowed.
    if config.block_final_hour_entries and local.hour >= 15:
        return False
    return True


def _exit_trade(
    bars: list[OHLCVBar], start_index: int, side: str, entry: float, stop: float, target: float, config: BacktestConfig
) -> tuple[int, float, str] | None:
    """Walk future bars. If stop and target occur in one bar, take the stop."""
    for index in range(start_index, len(bars)):
        bar = bars[index]
        if side == "long":
            stopped = bar.low <= stop
            targeted = bar.high >= target
        else:
            stopped = bar.high >= stop
            targeted = bar.low <= target
        if stopped:  # Conservative intrabar assumption.
            return index, _fill(stop, side, "stop", config.slippage_bps_per_side), "stop"
        if targeted:
            return index, _fill(target, side, "target", config.slippage_bps_per_side), "target"
        if config.force_friday_close and _is_friday_close(bar, config):
            return index, _fill(bar.close, side, "close", config.slippage_bps_per_side), "weekend_close"
    return None


def trade_costs(entry_price: float, exit_price: float, quantity: int, config: BacktestConfig) -> float:
    """Round-trip commission for one simulated trade under the config's cost model."""
    if config.commission_bps_per_side is not None:
        # Spot FX: commission is charged in bps of traded notional with a
        # per-order minimum, on each side at that side's fill price.
        fraction = config.commission_bps_per_side / 10_000
        entry_commission = max(entry_price * quantity * fraction, config.min_commission_per_order)
        exit_commission = max(exit_price * quantity * fraction, config.min_commission_per_order)
        return entry_commission + exit_commission
    commission = (
        config.commission_per_contract_per_side
        if config.commission_per_contract_per_side is not None
        else config.commission_per_share_per_side
    )
    return quantity * commission * 2


def run_backtest(
    entry_bars: Iterable[OHLCVBar],
    signals: Iterable[dict[str, object]],
    sizing_mode: SizingMode,
    config: BacktestConfig = BacktestConfig(),
) -> list[Trade]:
    """Simulate one open position at a time from precomputed candidate signals."""
    bars = list(entry_bars)
    by_timestamp = {bar.timestamp: index for index, bar in enumerate(bars)}
    equity = config.starting_equity
    rrms_tier = 0
    blocked = False
    next_free_index = 0
    trades: list[Trade] = []

    for signal in signals:
        if blocked:
            break
        entry_index = by_timestamp.get(str(signal["entry_timestamp"]))
        if entry_index is None or entry_index < next_free_index:
            continue
        side = str(signal["side"])
        if not _entry_allowed(bars[entry_index].timestamp, side, config):
            continue
        jaw = float(signal["jaw"])
        raw_entry = bars[entry_index].open
        entry = _fill(raw_entry, side, "entry", config.slippage_bps_per_side)
        stop = float(signal.get("stop_reference", jaw))
        price_risk = entry - stop if side == "long" else stop - entry
        risk_per_unit = price_risk * config.contract_multiplier
        if risk_per_unit <= 0:
            continue
        target = entry + price_risk if side == "long" else entry - price_risk
        risk_percent = config.fixed_risk_percent if sizing_mode == "fixed" else RRMS_TIERS[rrms_tier]
        risk_dollars = equity * risk_percent
        quantity = int(risk_dollars // risk_per_unit)
        if quantity < 1:
            continue

        exit_result = _exit_trade(bars, entry_index, side, entry, stop, target, config)
        if exit_result is None:
            # No completed exit is observable yet. Do not count an open trade
            # as a realised backtest result merely because the data ends.
            break
        exit_index, exit_price, exit_reason = exit_result
        direction = 1 if side == "long" else -1
        gross_pnl = quantity * (exit_price - entry) * direction * config.contract_multiplier
        costs = trade_costs(entry, exit_price, quantity, config)
        net_pnl = gross_pnl - costs
        planned_risk = quantity * risk_per_unit
        result_r = net_pnl / planned_risk
        equity += net_pnl
        trade = Trade(
            decision_timestamp=str(signal["decision_timestamp"]),
            entry_timestamp=bars[entry_index].timestamp,
            exit_timestamp=bars[exit_index].timestamp,
            side=side,
            rrms_tier=rrms_tier if sizing_mode == "rrms" else 0,
            quantity=quantity,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            exit_price=exit_price,
            exit_reason=exit_reason,
            gross_pnl=gross_pnl,
            costs=costs,
            net_pnl=net_pnl,
            result_r=result_r,
            equity_after=equity,
        )
        trades.append(trade)
        next_free_index = exit_index + 1

        if sizing_mode == "rrms":
            if exit_reason == "stop":
                if rrms_tier == len(RRMS_TIERS) - 1:
                    if config.rrms_reset_after_max_tier:
                        rrms_tier = 0
                    else:
                        blocked = True
                else:
                    rrms_tier += 1
            elif net_pnl > 0:
                rrms_tier = 0
    return trades


def summarize(trades: Iterable[Trade], starting_equity: float) -> dict[str, object]:
    rows = list(trades)
    gross_profit = sum(trade.net_pnl for trade in rows if trade.net_pnl > 0)
    gross_loss = sum(trade.net_pnl for trade in rows if trade.net_pnl < 0)
    equity = starting_equity
    peak = equity
    max_drawdown = 0.0
    for trade in rows:
        equity = trade.equity_after
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    long_rows = [trade for trade in rows if trade.side == "long"]
    short_rows = [trade for trade in rows if trade.side == "short"]
    return {
        "trade_count": len(rows),
        "wins": sum(trade.net_pnl > 0 for trade in rows),
        "losses": sum(trade.net_pnl < 0 for trade in rows),
        "win_rate": (sum(trade.net_pnl > 0 for trade in rows) / len(rows)) if rows else None,
        "net_pnl": sum(trade.net_pnl for trade in rows),
        "ending_equity": equity,
        "profit_factor": (gross_profit / abs(gross_loss)) if gross_loss else None,
        "average_r": mean(trade.result_r for trade in rows) if rows else None,
        "max_drawdown": max_drawdown,
        "long_trades": len(long_rows),
        "short_trades": len(short_rows),
        "exit_reasons": {reason: sum(trade.exit_reason == reason for trade in rows) for reason in sorted({trade.exit_reason for trade in rows})},
    }


def write_results(trades: Iterable[Trade], summary: dict[str, object], mode: SizingMode, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = list(trades)
    with (output / f"{mode}_trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else list(Trade.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    (output / f"{mode}_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Strategy 01 from local, read-only SPY bars.")
    parser.add_argument("--fifteen-minute", type=Path, default=Path("data/market_data/ibkr/SPY/spy_15m.csv"))
    parser.add_argument("--five-minute", type=Path, default=Path("data/market_data/ibkr/SPY/spy_5m.csv"))
    parser.add_argument("--one-hour", type=Path, default=Path("data/market_data/ibkr/SPY/spy_1h.csv"))
    parser.add_argument("--output", type=Path, default=Path("outputs/strategy_01_backtest"))
    parser.add_argument("--four-hour", type=Path, default=Path("data/market_data/ibkr/SPY/spy_4h.csv"))
    parser.add_argument("--profile", choices=("v1", "v2", "v3", "v3-weekend", "v3-mgc", "v4", "v5"), default="v1", help="Versioned historical test profile")
    args = parser.parse_args()
    is_v3 = args.profile in {"v3", "v3-weekend", "v3-mgc"}
    is_mgc = args.profile == "v3-mgc"
    is_v4 = args.profile in {"v4", "v5"}
    is_v5 = args.profile == "v5"
    bars = load_ohlcv_csv(args.one_hour if is_v3 else args.fifteen_minute)
    trend_bars = load_ohlcv_csv(args.four_hour if is_v3 else args.one_hour)
    signals = (
        candidate_signals_v5(bars, trend_bars, load_ohlcv_csv(args.five_minute))
        if is_v5
        else candidate_signals_v4(bars, trend_bars, load_ohlcv_csv(args.five_minute))
        if is_v4
        else candidate_signals(
            bars,
            trend_bars,
            entry_interval_minutes=60 if is_v3 else 15,
            trend_interval_minutes=240 if is_v3 else 60,
            minimum_decision_close_time=None if is_v3 else (10, 45),
            infer_trend_close_from_session_boundaries=is_v3 and not is_mgc,
            infer_shortened_trend_bars=is_mgc,
        )
    )
    config = (
        BacktestConfig(
            allowed_direction="long",
            block_friday_entries=True,
            entry_interval_minutes=60,
            contract_multiplier=10.0,
            # USD 0.70 COMEX non-member recovery plus USD 0.02 regulatory
            # recovery per side. Broker commission is not included yet.
            commission_per_contract_per_side=0.72,
            entry_window_start=(19, 0),
            entry_window_end=(16, 0),
            friday_close_time=(17, 0),
        )
        if is_mgc
        else
        BacktestConfig(
            allowed_direction="both",
            block_opening_hour_entries=True,
            block_final_hour_entries=True,
            block_friday_entries=True,
            entry_interval_minutes=15,
            rrms_reset_after_max_tier=is_v5,
        )
        if is_v4
        else
        BacktestConfig(
            allowed_direction="long",
            block_opening_hour_entries=is_v3,
            block_final_hour_entries=True,
            block_friday_entries=True,
            entry_interval_minutes=60 if is_v3 else 15,
            force_friday_close=args.profile != "v3-weekend",
        )
        if args.profile in {"v2", "v3", "v3-weekend"}
        else BacktestConfig()
    )
    eligible_signals = [
        signal
        for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]
    report = {
        "strategy_id": (
            "strategy_01_v3_mgc_bill_williams_alligator_rrms"
            if is_mgc
            else
            "strategy_01_v4_multi_timeframe_alligator"
            if args.profile == "v4"
            else "strategy_01_v5_dynamic_atr_jaw_buffer"
            if is_v5
            else
            "strategy_01_v3_weekend_bill_williams_alligator_rrms"
            if args.profile == "v3-weekend"
            else
            "strategy_01_v3_bill_williams_alligator_rrms"
            if args.profile == "v3"
            else "strategy_01_v2_bill_williams_alligator_rrms"
            if args.profile == "v2"
            else "strategy_01_bill_williams_alligator_rrms"
        ),
        "strategy_version": args.profile,
        "mode": "historical_backtest_only",
        "assumptions": {
            **asdict(config),
            "macro_filter": "not yet integrated: both directions are tested without a macro filter" if is_v4 else "manual bullish regime: long entries only" if args.profile in {"v2", "v3", "v3-weekend", "v3-mgc"} else "allowed (placeholder; no live macro data applied)",
            "entry": f"next {'1-hour' if is_v3 else '15-minute'} bar open after a completed signal bar",
            "timeframes": "1-hour confirmation / 15-minute entry / 5-minute momentum" if is_v4 else "4-hour confirmation / 1-hour entry" if is_v3 else "1-hour confirmation / 15-minute entry",
            "stop_buffer": "max($0.01 SPY tick, 0.10 x completed 15-minute ATR(14)) beyond Jaw" if is_v5 else "0.05% beyond completed 15-minute Jaw" if args.profile == "v4" else "strategy-specific",
            "session": "CME Globex 18:00-17:00 New York time; Sunday entry signals excluded" if is_mgc else "US regular trading hours",
            "opening_hour": "no new entries 18:00-19:00 New York time" if is_mgc else "no entry before 10:30 New York time" if is_v3 or is_v4 else "no entry before the first 1-hour RTH bar completes",
            "final_hour": "no new entries 16:00-17:00 New York time" if is_mgc else "no new entries from 15:00 New York time" if config.block_final_hour_entries else "allowed",
            "friday_entries": "blocked" if config.block_friday_entries else "allowed",
            "weekend": (
                "force-close in the final Friday bar containing 17:00 New York time"
                if is_mgc
                else
                "hold existing positions through the weekend"
                if not config.force_friday_close
                else "force-close in the final Friday entry-timeframe bar containing 16:00 New York time"
            ),
            "intrabar_collision": "stop assumed before target",
        },
        "candidate_signal_count": len(signals),
        "eligible_signal_count": len(eligible_signals),
        "results": {},
        "warning": (
            "Preliminary MGC result only. Continuous futures are research-only; "
            "the USD 0.72/side cost models IBKR's published exchange and regulatory "
            "fee recovery only, not your broker commission or roll costs."
            if is_mgc
            else "Preliminary result only. Parameters, macro filter, fee schedule, and market-impact model require validation before paper trading."
        ),
    }
    for mode in ("fixed", "rrms"):
        trades = run_backtest(bars, signals, mode, config)
        summary = summarize(trades, config.starting_equity)
        report["results"][mode] = summary
        write_results(trades, summary, mode, args.output)
    (args.output / "backtest_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved preliminary backtest report to {args.output / 'backtest_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
