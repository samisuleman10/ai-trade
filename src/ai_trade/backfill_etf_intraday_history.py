"""Resumable read-only IBKR intraday cache for QQQ and DIA (US30 proxy)."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_trade import market_data
from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, save_bars, us_etf_contract
from ai_trade.strategy_01 import load_ohlcv_csv


_original_error = market_data._HistoricalDataClient.error


def _gateway_error(self, req_id, error_code, error_string, advanced_order_reject_json=""):  # noqa: N802
    if error_code == 2107:  # IBKR says its historical farm is dormant but available on demand.
        return
    return _original_error(self, req_id, error_code, error_string, advanced_order_reject_json)


market_data._HistoricalDataClient.error = _gateway_error


def _as_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _asset(asset: str):
    if asset == "qqq":
        return us_etf_contract("QQQ", "NASDAQ"), "QQQ", Path("data/market_data/ibkr/QQQ/v5_5y")
    # DIA is the directly tradable ETF proxy for the Dow Jones Industrial Average / US30.
    return us_etf_contract("DIA", "ARCA"), "DIA", Path("data/market_data/ibkr/US30_DIA/v5_5y")


def _backfill(asset: str, timeframe: str, target: datetime, port: int, client_id: int, pause: float) -> None:
    contract, symbol, output = _asset(asset)
    duration, bar_size = {"5m": ("30 D", "5 mins"), "15m": ("90 D", "15 mins"), "1h": ("1 Y", "1 hour")}[timeframe]
    path = output / f"{symbol.lower()}_{timeframe}.csv"
    bars = load_ohlcv_csv(path) if path.exists() else []
    request_index = 0
    while not bars or _as_utc(bars[0].timestamp) > target:
        end = "" if not bars else _as_utc(bars[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
        incoming = fetch_historical_bars(
            contract=contract, duration=duration, bar_size=bar_size, host="127.0.0.1", port=port,
            client_id=client_id + request_index, use_rth=True, timeout=90, end_date_time=end,
        )
        combined = merge_bars(bars, incoming)
        if bars and combined[0].timestamp >= bars[0].timestamp:
            raise HistoricalDataError(f"{symbol} {timeframe} backfill made no progress at {bars[0].timestamp}.")
        bars = combined
        save_bars(bars, directory=output, symbol=symbol, timeframe=timeframe, source="ibkr_read_only_resumable_cache")
        print(f"{symbol} {timeframe}: {len(bars)} bars; earliest {bars[0].timestamp}", flush=True)
        request_index += 1
        time.sleep(pause)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill QQQ/DIA Strategy 02 data from the IBKR read-only API.")
    parser.add_argument("--assets", nargs="+", choices=("qqq", "dia"), default=("qqq", "dia"))
    parser.add_argument("--timeframes", nargs="+", choices=("5m", "15m", "1h"), default=("5m", "15m", "1h"))
    parser.add_argument("--target-start", default="2021-04-14")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=500)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        offset = 0
        for asset in args.assets:
            for timeframe in args.timeframes:
                _backfill(asset, timeframe, target, args.port, args.client_id + offset, args.pause_seconds)
                offset += 100
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
