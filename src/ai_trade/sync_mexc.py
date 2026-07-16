"""Command-line entry point for a read-only MEXC spot and futures sync."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_trade.mexc import MEXCSyncError, fetch_account, save_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a read-only MEXC spot and futures snapshot.")
    parser.add_argument("--output", type=Path, default=Path("data/mexc"))
    args = parser.parse_args()
    try:
        snapshot = fetch_account()
        path = save_snapshot(snapshot, args.output)
    except MEXCSyncError as error:
        parser.error(str(error))
    print(f"Saved {len(snapshot['spot']['balances'])} spot balances and {len(snapshot['futures']['positions'])} futures positions to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
