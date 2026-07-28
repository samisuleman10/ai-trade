"""CLI for previewing, transmitting, and cancelling IBKR paper orders."""

from __future__ import annotations

import argparse
import json

from ai_trade.ibkr_paper import BracketOrderRequest, PaperBroker, PaperExecutionError


def main() -> int:
    parser = argparse.ArgumentParser(description="Safety-gated IBKR paper bracket orders (port 7497 only).")
    parser.add_argument("--account", required=True, help="Exact IBKR paper account, normally beginning with DU")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=71)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bracket = subparsers.add_parser("bracket", help="Preview or transmit an attached entry/target/stop bracket")
    bracket.add_argument("--symbol", required=True)
    bracket.add_argument("--quantity", type=int, required=True)
    bracket.add_argument("--side", choices=("BUY", "SELL"), required=True)
    bracket.add_argument("--entry-type", choices=("MKT", "LMT"), default="LMT")
    bracket.add_argument("--limit-price", type=float)
    bracket.add_argument("--stop-price", type=float, required=True)
    bracket.add_argument("--target-price", type=float, required=True)
    bracket.add_argument("--tif", choices=("DAY", "GTC"), default="DAY")
    bracket.add_argument("--transmit", action="store_true", help="Actually send to the verified paper account")

    cancel = subparsers.add_parser("cancel", help="Cancel one API order in the verified paper account")
    cancel.add_argument("--order-id", type=int, required=True)

    args = parser.parse_args()
    broker = PaperBroker(
        expected_account=args.account, host=args.host, port=args.port, client_id=args.client_id
    )
    try:
        if args.command == "cancel":
            result = broker.cancel_order(args.order_id)
        else:
            request = BracketOrderRequest(
                symbol=args.symbol,
                quantity=args.quantity,
                side=args.side,
                entry_type=args.entry_type,
                limit_price=args.limit_price,
                stop_price=args.stop_price,
                target_price=args.target_price,
                time_in_force=args.tif,
            )
            result = broker.place_bracket(request, transmit=args.transmit)
    except PaperExecutionError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
