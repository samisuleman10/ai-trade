"""Download the maximum latest-window MGC continuous-futures history IBKR permits.

IBKR does not permit an ``endDateTime`` on a ``CONTFUT`` request.  This script
therefore requests one current, read-only window per timeframe.  It must not be
used to construct an order contract: continuous futures are research-only.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import ai_trade.market_data as market_data
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, mgc_continuous_contract, save_bars


def _ignore_dormant_hmds_farm() -> None:
    """Do not fail a request simply because IBKR reports its HMDS farm dormant."""
    original_error = market_data._HistoricalDataClient.error

    def error(self, req_id, error_time, error_code, error_string, advanced_order_reject_json=""):
        if error_code == 2107:
            return
        return original_error(self, req_id, error_time, error_code, error_string, advanced_order_reject_json)

    market_data._HistoricalDataClient.error = error


def _complete_bars(bars):
    return [bar for bar in bars if datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ").second == 0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Save the latest permissible MGC continuous-futures research history.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=75)
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/MGC/v5_5y"))
    parser.add_argument("--timeframes", nargs="+", choices=("15m", "1h"), default=("15m", "1h"))
    parser.add_argument("--fifteen-minute-duration", default="1 Y")
    parser.add_argument("--one-hour-duration", default="5 Y")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    _ignore_dormant_hmds_farm()
    definitions = {
        "15m": (args.fifteen_minute_duration, "15 mins"),
        "1h": (args.one_hour_duration, "1 hour"),
    }
    try:
        for timeframe in args.timeframes:
            duration, bar_size = definitions[timeframe]
            bars = fetch_historical_bars(
                contract=mgc_continuous_contract(), duration=duration, bar_size=bar_size,
                host=args.host, port=args.port, client_id=args.client_id,
                use_rth=False, timeout=args.timeout,
            )
            cleaned = _complete_bars(bars)
            csv_path, report_path = save_bars(cleaned, directory=args.output, symbol="MGC", timeframe=timeframe)
            first, last = cleaned[0].timestamp, cleaned[-1].timestamp
            print(f"{timeframe}: {len(cleaned)} bars from {first} to {last}; saved {csv_path} (validation: {report_path})")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
