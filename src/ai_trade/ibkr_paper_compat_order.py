"""Current-TWS compatible submission of one safety-gated paper order."""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from ibapi.client import EClient
from ibapi.order import Order
from ibapi.wrapper import EWrapper

from ai_trade.ibkr_paper import PaperExecutionError
from ai_trade.market_data import us_etf_contract


class _Client(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.accounts_ready = threading.Event()
        self.acknowledged = threading.Event()
        self.next_order_id: int | None = None
        self.accounts: list[str] = []
        self.errors: list[str] = []
        self.statuses: list[dict[str, Any]] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_order_id = orderId
        self.ready.set()

    def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
        self.accounts = [item.strip() for item in accountsList.split(",") if item.strip()]
        self.accounts_ready.set()

    def error(  # noqa: N802
        self, reqId: int, errorTime: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""
    ) -> None:
        if errorCode not in {2104, 2106, 2107, 2108, 2158}:
            self.errors.append(f"IBKR {errorCode} (request {reqId}): {errorString}")
            self.acknowledged.set()

    def orderStatus(
        self, orderId: int, status: str, filled: Decimal, remaining: Decimal,
        avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
        clientId: int, whyHeld: str, mktCapPrice: float,
    ) -> None:  # noqa: N802
        self.statuses.append(
            {
                "order_id": orderId,
                "status": status,
                "filled": str(filled),
                "remaining": str(remaining),
                "average_fill_price": avgFillPrice,
                "permanent_id": permId,
            }
        )
        if status in {"PreSubmitted", "Submitted", "Filled", "Inactive"}:
            self.acknowledged.set()


def submit_paper_market_order(
    *, account: str, symbol: str, side: str, quantity: int,
    host: str = "localhost", port: int = 7497, client_id: int = 71,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if port != 7497 or not account.upper().startswith("DU"):
        raise PaperExecutionError("paper submission requires port 7497 and a DU account")
    if side.upper() not in {"BUY", "SELL"} or quantity <= 0:
        raise PaperExecutionError("side must be BUY or SELL and quantity must be positive")
    app = _Client()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-paper-compatible-order", daemon=True)
    thread.start()
    try:
        if not app.ready.wait(timeout) or not app.accounts_ready.wait(timeout):
            raise PaperExecutionError("paper connection timed out")
        if account not in app.accounts or any(not item.upper().startswith("DU") for item in app.accounts):
            raise PaperExecutionError("connected account did not pass paper-account verification")
        assert app.next_order_id is not None
        order = Order()
        order.account = account
        order.action = side.upper()
        order.totalQuantity = Decimal(quantity)
        order.orderType = "MKT"
        order.tif = "DAY"
        order.transmit = True
        order.eTradeOnly = False
        order.firmQuoteOnly = False
        app.placeOrder(app.next_order_id, us_etf_contract(symbol, "ARCA"), order)
        if not app.acknowledged.wait(timeout):
            raise PaperExecutionError("order acknowledgement timed out")
        if app.errors:
            raise PaperExecutionError("; ".join(app.errors))
        return {"order_id": app.next_order_id, "account": account, "symbol": symbol, "statuses": app.statuses}
    finally:
        if app.isConnected():
            app.disconnect()
        thread.join(timeout=1)
