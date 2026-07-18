"""Resumable, read-only multi-timeframe SPY history cache for Strategy 01 v4."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_trade.market_data import HistoricalDataError, OHLCVBar, fetch_historical_bars, save_bars, spy_contract
from ai_trade.strategy_01 import load_ohlcv_csv


CHUNKS = {"5m": ("30 D", "5 mins"), "15m": ("90 D", "15 mins"), "1h": ("1 Y", "1 hour")}


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def merge_bars(existing: list[OHLCVBar], incoming: list[OHLCVBar]) -> list[OHLCVBar]:
    """Merge cached and incoming bars by timestamp without duplicate rows."""
    merged = {bar.timestamp: bar for bar in existing}
    merged.update({bar.timestamp: bar for bar in incoming})
    return [merged[timestamp] for timestamp in sorted(merged)]


def backfill_timeframe(
    *,
    timeframe: str,
    directory: Path,
    target_start: datetime,
    port: int,
    client_id: int,
    pause_seconds: float,
) -> int:
    duration, bar_size = CHUNKS[timeframe]
    csv_path = directory / f"spy_{timeframe}.csv"
    cached = load_ohlcv_csv(csv_path) if csv_path.exists() else []
    before = len(cached)
    request_number = 0
    while not cached or _time(cached[0].timestamp) > target_start:
        # IBKR's UTC request form uses a dash between date and time and does
        # not append a timezone token.
        end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
        incoming = fetch_historical_bars(
            contract=spy_contract(), duration=duration, bar_size=bar_size, port=port,
            client_id=client_id + request_number, use_rth=True, timeout=90, end_date_time=end,
        )
        merged = merge_bars(cached, incoming)
        if cached and merged[0].timestamp >= cached[0].timestamp:
            raise HistoricalDataError(f"{timeframe} backfill made no progress at {cached[0].timestamp}.")
        cached = merged
        save_bars(cached, directory=directory, symbol="SPY", timeframe=timeframe, source="ibkr_read_only_resumable_cache")
        request_number += 1
        print(f"{timeframe}: {len(cached)} cached bars; earliest {cached[0].timestamp}")
        if _time(cached[0].timestamp) <= target_start:
            break
        time.sleep(pause_seconds)
    return len(cached) - before


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill a local V4 SPY cache with read-only IBKR historical bars.")
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y"))
    parser.add_argument("--target-start", default="2024-07-17", help="UTC calendar date to reach, YYYY-MM-DD.")
    parser.add_argument("--port", type=int, default=7496)
    parser.add_argument("--client-id", type=int, default=90)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--timeframes", nargs="+", choices=tuple(CHUNKS), default=tuple(CHUNKS))
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        for offset, timeframe in enumerate(args.timeframes):
            added = backfill_timeframe(
                timeframe=timeframe, directory=args.output, target_start=target, port=args.port,
                client_id=args.client_id + offset * 30, pause_seconds=args.pause_seconds,
            )
            print(f"{timeframe}: added {added} bars; cache retained locally at {args.output}")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
