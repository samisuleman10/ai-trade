"""Gateway quote snapshots supporting both live and delayed IBKR tick fields."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from ai_trade.ibkr_quote import QuoteError
from ai_trade.market_data import us_etf_contract


class _GatewayQuoteClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.complete = threading.Event()
        self.prices: dict[str, float] = {}
        self.market_data_type: int | None = None
        self.warnings: list[str] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.connected.set()

    def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802
        self.market_data_type = marketDataType

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib) -> None:  # noqa: N802
        names = {
            1: "bid", 2: "ask", 4: "last", 6: "high", 7: "low", 9: "close",
            66: "bid", 67: "ask", 68: "last", 72: "high", 73: "low", 75: "close",
        }
        if tickType in names and price >= 0:
            self.prices[names[tickType]] = price

    def tickSnapshotEnd(self, reqId: int) -> None:  # noqa: N802
        self.complete.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        if errorCode not in {2104, 2106, 2107, 2108, 2119, 2158}:
            self.warnings.append(f"IBKR {errorCode} (request {reqId}): {errorString}")
            if errorCode in {10089, 10168, 354}:
                self.complete.set()


def fetch_gateway_quote(
    symbol: str, *, host: str = "localhost", port: int = 4001,
    client_id: int = 83, timeout: float = 15.0,
) -> dict[str, Any]:
    app = _GatewayQuoteClient()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-gateway-quote", daemon=True)
    thread.start()
    try:
        if not app.connected.wait(timeout):
            raise QuoteError("Gateway connection timed out")
        app.reqMarketDataType(3)
        app.reqMktData(8301, us_etf_contract(symbol, "NASDAQ"), "", True, False, [])
        if not app.complete.wait(timeout):
            raise QuoteError("; ".join(app.warnings) or "quote snapshot timed out")
        if not app.prices:
            raise QuoteError("; ".join(app.warnings) or "IBKR returned no quote prices")
        types = {1: "live", 2: "frozen", 3: "delayed", 4: "delayed_frozen"}
        return {
            "symbol": symbol.upper(),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "market_data_type": types.get(app.market_data_type, f"unknown_{app.market_data_type}"),
            **app.prices,
            "warnings": app.warnings,
        }
    finally:
        if app.isConnected():
            app.cancelMktData(8301)
            app.disconnect()
        thread.join(timeout=1)
