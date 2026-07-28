"""Resumable, read-only CBOE VIX 15-minute history cache."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ibapi.contract import Contract

from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, save_bars
from ai_trade.strategy_01 import load_ohlcv_csv


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def vix_contract() -> Contract:
    contract = Contract()
    contract.symbol = "VIX"
    contract.secType = "IND"
    contract.exchange = "CBOE"
    contract.currency = "USD"
    return contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill read-only 15-minute VIX index bars from IBKR.")
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/VIX/v2"))
    parser.add_argument("--target-start", default="2024-07-17")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=230)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    csv_path = args.output / "vix_15m.csv"
    cached = load_ohlcv_csv(csv_path) if csv_path.exists() else []
    try:
        request = 0
        while not cached or _time(cached[0].timestamp) > target:
            end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
            incoming = fetch_historical_bars(
                contract=vix_contract(), duration="90 D", bar_size="15 mins", port=args.port,
                client_id=args.client_id + request, use_rth=True, timeout=90, end_date_time=end,
            )
            merged = merge_bars(cached, incoming)
            if cached and merged[0].timestamp >= cached[0].timestamp:
                raise HistoricalDataError(f"VIX 15-minute backfill made no progress at {cached[0].timestamp}.")
            cached = merged
            save_bars(cached, directory=args.output, symbol="VIX", timeframe="15m", source="ibkr_read_only_resumable_cache")
            print(f"VIX 15m: {len(cached)} cached bars; earliest {cached[0].timestamp}")
            request += 1
            time.sleep(args.pause_seconds)
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
