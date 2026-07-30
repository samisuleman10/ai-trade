"""Save IBKR's latest permitted MGC continuous-futures intraday window.

Continuous futures are research-only and IBKR does not allow an end time on
their history requests, so this intentionally does not attempt a backfill.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import ai_trade.market_data as market_data
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, mgc_continuous_contract, save_bars


_original_error = market_data._HistoricalDataClient.error


def _gateway_error(self, req_id, error_time, error_code, error_string, advanced_order_reject_json=""):  # noqa: N802
    if error_code == 2107:
        return
    return _original_error(self, req_id, error_time, error_code, error_string, advanced_order_reject_json)


market_data._HistoricalDataClient.error = _gateway_error


def main() -> int:
    parser = argparse.ArgumentParser(description="Download latest read-only MGC continuous-futures intraday bars.")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=650)
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/MGC/v5_5y"))
    parser.add_argument("--timeframes", nargs="+", choices=("5m", "15m", "1h"), default=("5m", "15m", "1h"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    definitions = {"5m": ("30 D", "5 mins"), "15m": ("90 D", "15 mins"), "1h": ("3 Y", "1 hour")}
    try:
        for offset, timeframe in enumerate(args.timeframes):
            duration, bar_size = definitions[timeframe]
            bars = fetch_historical_bars(
                contract=mgc_continuous_contract(), duration=duration, bar_size=bar_size,
                host="127.0.0.1", port=args.port, client_id=args.client_id + offset,
                use_rth=False, timeout=args.timeout,
            )
            complete = [bar for bar in bars if datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ").second == 0]
            path, _ = save_bars(complete, directory=args.output, symbol="MGC", timeframe=timeframe, source="ibkr_continuous_research_only")
            print(f"MGC {timeframe}: {len(complete)} bars; {complete[0].timestamp} to {complete[-1].timestamp}; {path}")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
