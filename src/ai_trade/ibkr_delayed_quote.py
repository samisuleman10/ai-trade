"""Delayed-capable TWS quote snapshot compatibility helper."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ai_trade.ibkr_quote import QuoteError, _QuoteClient
from ai_trade.market_data import us_etf_contract


class _DelayedQuoteClient(_QuoteClient):
    def error(  # noqa: N802
        self, reqId: int, errorTime: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""
    ) -> None:
        if errorCode not in {2104, 2106, 2107, 2108, 2119, 2158}:
            self.errors.append(f"IBKR {errorCode} (request {reqId}): {errorString}")
            if errorCode in {10089, 10168, 354}:
                self.complete.set()


def fetch_delayed_quote(
    symbol: str, *, host: str = "localhost", port: int = 4001,
    client_id: int = 82, timeout: float = 15.0,
) -> dict[str, Any]:
    app = _DelayedQuoteClient()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-delayed-quote", daemon=True)
    thread.start()
    try:
        if not app.connected.wait(timeout):
            raise QuoteError("; ".join(app.errors) or "TWS connection timed out")
        app.reqMarketDataType(3)
        app.reqMktData(8201, us_etf_contract(symbol, "NASDAQ"), "", True, False, [])
        if not app.complete.wait(timeout):
            raise QuoteError("; ".join(app.errors) or "quote snapshot timed out")
        if not app.prices:
            raise QuoteError("; ".join(app.errors) or "IBKR returned no quote prices")
        types = {1: "live", 2: "frozen", 3: "delayed", 4: "delayed_frozen"}
        return {
            "symbol": symbol.upper(),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "market_data_type": types.get(app.market_data_type, f"unknown_{app.market_data_type}"),
            **app.prices,
            "warnings": app.errors,
        }
    finally:
        if app.isConnected():
            app.cancelMktData(8201)
            app.disconnect()
        thread.join(timeout=1)
