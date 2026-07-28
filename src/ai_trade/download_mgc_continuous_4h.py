"""Save the latest available 4-hour IBKR continuous MGC research history."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import ai_trade.market_data as market_data
from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, mgc_continuous_contract, save_bars


_original_error = market_data._HistoricalDataClient.error


def _gateway_error(self, req_id, error_code, error_string, advanced_order_reject_json=""):  # noqa: N802
    if error_code == 2107:
        return
    return _original_error(self, req_id, error_code, error_string, advanced_order_reject_json)


market_data._HistoricalDataClient.error = _gateway_error


def main() -> int:
    parser = argparse.ArgumentParser(description="Download latest continuous MGC 4-hour research bars from IBKR.")
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=1450)
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/MGC/v5_5y"))
    parser.add_argument("--duration", default="5 Y")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        bars = fetch_historical_bars(
            contract=mgc_continuous_contract(), duration=args.duration, bar_size="4 hours",
            host="127.0.0.1", port=args.port, client_id=args.client_id,
            use_rth=False, timeout=args.timeout,
        )
        complete = [bar for bar in bars if datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ").second == 0]
        path, _ = save_bars(complete, directory=args.output, symbol="MGC", timeframe="4h", source="ibkr_continuous_research_only")
        print(f"MGC 4h: {len(complete)} bars; {complete[0].timestamp} to {complete[-1].timestamp}; {path}")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
