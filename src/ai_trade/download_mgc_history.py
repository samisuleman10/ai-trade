"""Read-only continuous Micro Gold futures historical-data collection."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, mgc_continuous_contract, save_bars


def _drop_partial_bars(bars):
    """Discard IBKR's occasional leading partial bar from a rolling request."""
    kept = []
    for bar in bars:
        stamp = datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ")
        if stamp.second != 0:
            continue
        kept.append(bar)
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description="Download research-only continuous MGC historical bars from IBKR.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=51)
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/MGC/v3_2y"))
    parser.add_argument("--one-hour-duration", default="2 Y")
    parser.add_argument("--four-hour-duration", default="2 Y")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--timeframes", nargs="+", choices=("1h", "4h"), default=("1h", "4h"))
    args = parser.parse_args()

    definitions = {
        "1h": (args.one_hour_duration, "1 hour"),
        "4h": (args.four_hour_duration, "4 hours"),
    }
    try:
        for timeframe in args.timeframes:
            duration, bar_size = definitions[timeframe]
            bars = fetch_historical_bars(
                contract=mgc_continuous_contract(),
                duration=duration,
                bar_size=bar_size,
                host=args.host,
                port=args.port,
                client_id=args.client_id,
                use_rth=False,
                timeout=args.timeout,
            )
            cleaned = _drop_partial_bars(bars)
            csv_path, report_path = save_bars(cleaned, directory=args.output, symbol="MGC", timeframe=timeframe)
            print(f"{timeframe}: saved {len(cleaned)} complete bars to {csv_path} (validation: {report_path})")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
