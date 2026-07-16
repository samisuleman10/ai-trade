"""Command-line entry point for a read-only IBKR portfolio sync."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_trade.ibkr import IBKRSyncError, fetch_portfolio, save_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a read-only IBKR portfolio snapshot.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497, help="7497 paper TWS; 7496 live TWS")
    parser.add_argument("--client-id", type=int, default=17)
    parser.add_argument("--output", type=Path, default=Path("data/portfolio"))
    args = parser.parse_args()
    try:
        snapshot = fetch_portfolio(args.host, args.port, args.client_id)
        path = save_snapshot(snapshot, args.output)
    except IBKRSyncError as error:
        parser.error(str(error))
    print(f"Saved {len(snapshot['positions'])} positions to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
