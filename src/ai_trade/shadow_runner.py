"""Read-only IBKR data runner for Strategy 01 v3 shadow trading.

It can refresh a small local SPY snapshot and invoke the local-only shadow
cycle. It deliberately contains no order, account, position, or execution API.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, save_bars, spy_contract
from ai_trade.shadow_monitor import monitor_positions, next_rrms_tier, open_positions
from ai_trade.shadow_trading import ShadowCycleConfig, run_cycle


NEW_YORK = ZoneInfo("America/New_York")
DECISION_TIMES = ((10, 30), (11, 30), (12, 30), (13, 30), (14, 30))


def scheduled_decision_timestamp(now: datetime, grace_minutes: int = 5) -> str | None:
    """Return the due New York decision timestamp, otherwise ``None``.

    The short grace window lets the current 1-hour opening bar reach IBKR's
    historical feed. The shadow-cycle duplicate guard makes retry safe.
    """
    local = now.astimezone(NEW_YORK)
    if local.weekday() > 3:
        return None
    for hour, minute in DECISION_TIMES:
        due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= local < due + timedelta(minutes=grace_minutes):
            return due.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def refresh_snapshot(*, directory: Path, port: int, client_id: int) -> tuple[Path, Path]:
    """Make two read-only historical-data requests and save a local snapshot."""
    contract = spy_contract()
    one_hour = fetch_historical_bars(
        contract=contract, duration="60 D", bar_size="1 hour", port=port, client_id=client_id, use_rth=True, timeout=60
    )
    four_hour = fetch_historical_bars(
        contract=contract, duration="120 D", bar_size="4 hours", port=port, client_id=client_id + 1, use_rth=True, timeout=60
    )
    one_hour_path, _ = save_bars(one_hour, directory=directory, symbol="SPY", timeframe="1h", source="ibkr_read_only_shadow")
    four_hour_path, _ = save_bars(four_hour, directory=directory, symbol="SPY", timeframe="4h", source="ibkr_read_only_shadow")
    return one_hour_path, four_hour_path


def run_due_cycle(
    *,
    decision_timestamp: str,
    snapshot_directory: Path,
    output_directory: Path,
    port: int,
    client_id: int,
    config: ShadowCycleConfig,
    force_weekend_close: bool = False,
) -> dict[str, object]:
    one_hour, four_hour = refresh_snapshot(directory=snapshot_directory, port=port, client_id=client_id)
    from ai_trade.strategy_01 import load_ohlcv_csv

    exits = monitor_positions(
        bars=load_ohlcv_csv(one_hour),
        cutoff_timestamp=decision_timestamp,
        output_directory=output_directory,
        force_weekend_close=force_weekend_close,
    )
    rrms_tier = next_rrms_tier(output_directory) if config.rrms_tier < 0 else config.rrms_tier
    active = open_positions(output_directory)
    return run_cycle(
        one_hour_path=one_hour,
        four_hour_path=four_hour,
        decision_timestamp=decision_timestamp,
        output_directory=output_directory,
        config=ShadowCycleConfig(config.macro_stance, config.simulated_equity, rrms_tier),
        preflight_rejection="open_shadow_position_exists" if active else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only Strategy 01 v3 shadow cycles; no broker orders exist in this command.")
    parser.add_argument("--port", type=int, default=7496, help="TWS/IB Gateway API socket port; data requests only.")
    parser.add_argument("--client-id", type=int, default=71)
    parser.add_argument("--snapshot-directory", type=Path, default=Path("data/shadow_trading/strategy_01/v3/spy/current"))
    parser.add_argument("--output", type=Path, default=Path("outputs/shadow_trading/strategy_01/v3/spy/live_forward"))
    parser.add_argument("--macro-stance", choices=("bullish", "neutral", "bearish"), default="bullish")
    parser.add_argument("--simulated-equity", type=float, default=100_000.0)
    parser.add_argument("--rrms-tier", type=int, default=-1, help="Use -1 to derive tier from the local closed-trade ledger (default).")
    parser.add_argument("--force-weekend-close", action="store_true", help="Close any open shadow position using the latest completed Friday bar.")
    parser.add_argument("--once", action="store_true", help="Run one named decision timestamp, useful for a safe manual check.")
    parser.add_argument("--decision-timestamp", help="Required with --once; ISO UTC timestamp of the new 1-hour bar.")
    parser.add_argument("--serve", action="store_true", help="Check the New York schedule once per minute; only act in the five permitted windows.")
    args = parser.parse_args()
    if args.once == args.serve:
        parser.error("Choose exactly one of --once or --serve.")
    if args.once and not args.decision_timestamp:
        parser.error("--once requires --decision-timestamp.")
    config = ShadowCycleConfig(args.macro_stance, args.simulated_equity, args.rrms_tier)

    def attempt(timestamp: str) -> bool:
        try:
            result = run_due_cycle(
                decision_timestamp=timestamp,
                snapshot_directory=args.snapshot_directory,
                output_directory=args.output,
                port=args.port,
                client_id=args.client_id,
                config=config,
                force_weekend_close=args.force_weekend_close,
            )
            print(result)
            return True
        except (HistoricalDataError, ValueError) as error:
            # A data failure is intentionally non-trading: it is visible to the
            # operator, and the next scheduled minute may retry during grace.
            print({"status": "data_error", "decision_timestamp": timestamp, "reason": str(error)})
            return False

    if args.once:
        attempt(args.decision_timestamp)
        return 0
    processed_timestamps: set[str] = set()
    while True:
        timestamp = scheduled_decision_timestamp(datetime.now(timezone.utc))
        if timestamp and timestamp not in processed_timestamps and attempt(timestamp):
            processed_timestamps.add(timestamp)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
