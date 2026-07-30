"""Resumable, read-only five-year history cache for Strategy 02 assets."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_trade import market_data
from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, mgc_continuous_contract, save_bars, us_etf_contract
from ai_trade.strategy_01 import load_ohlcv_csv


_original_error = market_data._HistoricalDataClient.error


def _gateway_error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson="") -> None:  # noqa: N802
    if errorCode == 2107:  # Historical-data farm available on demand.
        return
    _original_error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)


market_data._HistoricalDataClient.error = _gateway_error


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _details(asset: str):
    if asset == "qqq":
        return us_etf_contract("QQQ", "NASDAQ"), "QQQ", True, Path("data/market_data/ibkr/QQQ/v5_5y")
    return mgc_continuous_contract(), "MGC", False, Path("data/market_data/ibkr/MGC/v5_5y")


def _backfill(asset: str, timeframe: str, target: datetime, port: int, client_id: int, pause: float) -> None:
    contract, symbol, use_rth, directory = _details(asset)
    duration, bar_size = {"15m": ("90 D", "15 mins"), "1h": ("1 Y", "1 hour")}[timeframe]
    path = directory / f"{symbol.lower()}_{timeframe}.csv"
    cached = load_ohlcv_csv(path) if path.exists() else []
    request = 0
    while not cached or _time(cached[0].timestamp) > target:
        end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
        incoming = fetch_historical_bars(
            contract=contract, duration=duration, bar_size=bar_size, port=port,
            client_id=client_id + request, use_rth=use_rth, timeout=90, end_date_time=end,
        )
        merged = merge_bars(cached, incoming)
        if cached and merged[0].timestamp >= cached[0].timestamp:
            raise HistoricalDataError(f"{symbol} {timeframe} backfill made no progress at {cached[0].timestamp}.")
        cached = merged
        save_bars(cached, directory=directory, symbol=symbol, timeframe=timeframe, source="ibkr_read_only_resumable_cache")
        print(f"{symbol} {timeframe}: {len(cached)} bars; earliest {cached[0].timestamp}", flush=True)
        request += 1
        time.sleep(pause)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill QQQ/MGC Strategy 02 history from IBKR read-only API.")
    parser.add_argument("--assets", nargs="+", choices=("qqq", "mgc"), default=("qqq", "mgc"))
    parser.add_argument("--timeframes", nargs="+", choices=("15m", "1h"), default=("15m", "1h"))
    parser.add_argument("--target-start", default="2021-04-14")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=300)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        offset = 0
        for asset in args.assets:
            for timeframe in args.timeframes:
                _backfill(asset, timeframe, target, args.port, args.client_id + offset, args.pause_seconds)
                offset += 80
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
