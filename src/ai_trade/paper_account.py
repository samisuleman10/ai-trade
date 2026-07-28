"""Command-line operations for a verified IBKR paper account."""

from __future__ import annotations

import argparse
import json

from ai_trade.ibkr_paper import PaperExecutionError
from ai_trade.ibkr_paper_operations import PaperAccountOperations, PaperOrderRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage an IBKR paper account; live port 7496 is rejected.")
    parser.add_argument("--account", required=True, help="Exact paper account ID beginning with DU")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=71)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("orders", help="List open orders owned by this API client ID")
    commands.add_parser("executions", help="List executions visible to this paper session")
    commands.add_parser("positions", help="List current paper positions")

    place = commands.add_parser("place", help="Preview or place a standalone market/limit order")
    place.add_argument("--symbol", required=True)
    place.add_argument("--side", choices=("BUY", "SELL"), required=True)
    place.add_argument("--quantity", type=int, required=True)
    place.add_argument("--order-type", choices=("MKT", "LMT"), default="LMT")
    place.add_argument("--limit-price", type=float)
    place.add_argument("--tif", choices=("DAY", "GTC"), default="DAY")
    place.add_argument("--transmit", action="store_true")

    modify = commands.add_parser("modify", help="Preview or modify an open API-owned order")
    modify.add_argument("--order-id", type=int, required=True)
    modify.add_argument("--quantity", type=int)
    modify.add_argument("--limit-price", type=float)
    modify.add_argument("--transmit", action="store_true")

    cancel = commands.add_parser("cancel", help="Preview or cancel one API-owned order")
    cancel.add_argument("--order-id", type=int, required=True)
    cancel.add_argument("--transmit", action="store_true")

    cancel_all = commands.add_parser("cancel-all", help="Preview or cancel all API-owned orders")
    cancel_all.add_argument("--transmit", action="store_true")

    close = commands.add_parser("close", help="Preview or market-close one complete paper position")
    close.add_argument("--symbol", required=True)
    close.add_argument("--transmit", action="store_true")

    args = parser.parse_args()
    broker = PaperAccountOperations(
        expected_account=args.account, host=args.host, port=args.port, client_id=args.client_id
    )
    try:
        if args.command == "orders":
            result = broker.list_open_orders()
        elif args.command == "executions":
            result = broker.list_executions()
        elif args.command == "positions":
            result = broker.list_positions()
        elif args.command == "place":
            result = broker.place_order(
                PaperOrderRequest(
                    symbol=args.symbol,
                    side=args.side,
                    quantity=args.quantity,
                    order_type=args.order_type,
                    limit_price=args.limit_price,
                    time_in_force=args.tif,
                ),
                transmit=args.transmit,
            )
        elif args.command == "modify":
            result = broker.modify_order(
                args.order_id, quantity=args.quantity, limit_price=args.limit_price, transmit=args.transmit
            )
        elif args.command == "cancel":
            result = broker.cancel_order(args.order_id, transmit=args.transmit)
        elif args.command == "cancel-all":
            result = broker.cancel_all(transmit=args.transmit)
        else:
            result = broker.close_position(args.symbol, transmit=args.transmit)
    except PaperExecutionError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
