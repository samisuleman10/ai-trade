"""CLI for read-only SPY historical-data collection from TWS/IB Gateway."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_trade.market_data import HistoricalDataError, fetch_historical_bars, save_bars, us_etf_contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Download read-only US ETF historical bars from IBKR.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497, help="7497 paper TWS; 7496 live TWS")
    parser.add_argument("--client-id", type=int, default=31)
    parser.add_argument("--symbol", default="SPY", help="US ETF ticker (default: SPY).")
    parser.add_argument("--primary-exchange", default="ARCA", help="Primary listing exchange (default: ARCA).")
    parser.add_argument("--output", type=Path, default=Path("data/market_data/ibkr/SPY"))
    parser.add_argument("--rth-only", action="store_true", default=True, help="Use regular trading hours only (default).")
    parser.add_argument("--include-extended-hours", action="store_true", help="Include extended-hours bars.")
    parser.add_argument("--five-minute-duration", default="60 D")
    parser.add_argument("--fifteen-minute-duration", default="60 D")
    parser.add_argument("--one-hour-duration", default="365 D")
    parser.add_argument("--four-hour-duration", default="2 Y")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        choices=("5m", "15m", "1h", "4h"),
        default=("15m", "1h"),
        help="One or more bar sets to download (default: 15m 1h).",
    )
    args = parser.parse_args()
    use_rth = args.rth_only and not args.include_extended_hours

    try:
        definitions = {
            "5m": (args.five_minute_duration, "5 mins"),
            "15m": (args.fifteen_minute_duration, "15 mins"),
            "1h": (args.one_hour_duration, "1 hour"),
            "4h": (args.four_hour_duration, "4 hours"),
        }
        for timeframe in args.timeframes:
            duration, bar_size = definitions[timeframe]
            bars = fetch_historical_bars(
                contract=us_etf_contract(args.symbol, args.primary_exchange),
                duration=duration,
                bar_size=bar_size,
                host=args.host,
                port=args.port,
                client_id=args.client_id,
                use_rth=use_rth,
            )
            csv_path, report_path = save_bars(bars, directory=args.output, symbol=args.symbol, timeframe=timeframe)
            print(f"{timeframe}: saved {len(bars)} bars to {csv_path} (validation: {report_path})")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
