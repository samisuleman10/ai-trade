"""Resumable, read-only QQQ 15-minute history cache for Strategy 02 tests."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, save_bars, us_etf_contract
from ai_trade.strategy_01 import load_ohlcv_csv


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill local QQQ 15-minute bars from IBKR read-only history.")
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/QQQ/v3_2y"))
    parser.add_argument("--target-start", default="2024-07-17")
    parser.add_argument("--port", type=int, default=7496)
    parser.add_argument("--client-id", type=int, default=180)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    csv_path = args.output / "qqq_15m.csv"
    cached = load_ohlcv_csv(csv_path) if csv_path.exists() else []
    contract = us_etf_contract("QQQ", "NASDAQ")
    try:
        request = 0
        while not cached or _time(cached[0].timestamp) > target:
            end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
            incoming = fetch_historical_bars(
                contract=contract, duration="90 D", bar_size="15 mins", port=args.port,
                client_id=args.client_id + request, use_rth=True, timeout=90, end_date_time=end,
            )
            merged = merge_bars(cached, incoming)
            if cached and merged[0].timestamp >= cached[0].timestamp:
                raise HistoricalDataError(f"QQQ 15-minute backfill made no progress at {cached[0].timestamp}.")
            cached = merged
            save_bars(cached, directory=args.output, symbol="QQQ", timeframe="15m", source="ibkr_read_only_resumable_cache")
            print(f"QQQ 15m: {len(cached)} cached bars; earliest {cached[0].timestamp}")
            request += 1
            time.sleep(args.pause_seconds)
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
