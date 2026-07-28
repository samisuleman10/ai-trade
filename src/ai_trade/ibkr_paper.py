"""Safety-gated order execution for an IBKR paper account only."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.wrapper import EWrapper

from ai_trade.market_data import us_etf_contract


class PaperExecutionError(RuntimeError):
    """Raised when paper-account verification or an order operation fails."""


@dataclass(frozen=True)
class BracketOrderRequest:
    symbol: str
    quantity: int
    side: str
    entry_type: str
    stop_price: float
    target_price: float
    limit_price: float | None = None
    time_in_force: str = "DAY"

    def validate(self) -> None:
        side = self.side.upper()
        entry_type = self.entry_type.upper()
        if side not in {"BUY", "SELL"}:
            raise PaperExecutionError("side must be BUY or SELL")
        if entry_type not in {"MKT", "LMT"}:
            raise PaperExecutionError("entry_type must be MKT or LMT")
        if self.quantity <= 0:
            raise PaperExecutionError("quantity must be a positive whole number")
        if self.stop_price <= 0 or self.target_price <= 0:
            raise PaperExecutionError("stop and target prices must be positive")
        if entry_type == "LMT" and (self.limit_price is None or self.limit_price <= 0):
            raise PaperExecutionError("a positive limit_price is required for LMT entry")
        if self.limit_price is not None:
            if side == "BUY" and not self.stop_price < self.limit_price < self.target_price:
                raise PaperExecutionError("BUY bracket requires stop < entry < target")
            if side == "SELL" and not self.target_price < self.limit_price < self.stop_price:
                raise PaperExecutionError("SELL bracket requires target < entry < stop")
        if self.time_in_force.upper() not in {"DAY", "GTC"}:
            raise PaperExecutionError("time_in_force must be DAY or GTC")


class _PaperClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.accounts_received = threading.Event()
        self.order_complete = threading.Event()
        self.cancel_complete = threading.Event()
        self.next_order_id: int | None = None
        self.accounts: list[str] = []
        self.errors: list[str] = []
        self.order_events: list[dict[str, Any]] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_order_id = orderId
        self.connected.set()

    def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
        self.accounts = [value.strip() for value in accountsList.split(",") if value.strip()]
        self.accounts_received.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        if errorCode not in {2104, 2106, 2107, 2108, 2158}:
            detail = f"IBKR {errorCode} (request {reqId}): {errorString}"
            if advancedOrderRejectJson:
                detail += f" reject={advancedOrderRejectJson}"
            self.errors.append(detail)
            self.order_complete.set()
            self.cancel_complete.set()

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState) -> None:  # noqa: N802
        self.order_events.append(
            {
                "event": "open_order",
                "order_id": orderId,
                "symbol": contract.symbol,
                "action": order.action,
                "quantity": str(order.totalQuantity),
                "order_type": order.orderType,
                "status": orderState.status,
            }
        )

    def orderStatus(
        self, orderId: int, status: str, filled: Decimal, remaining: Decimal,
        avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
        clientId: int, whyHeld: str, mktCapPrice: float,
    ) -> None:  # noqa: N802
        self.order_events.append(
            {
                "event": "order_status",
                "order_id": orderId,
                "status": status,
                "filled": str(filled),
                "remaining": str(remaining),
                "average_fill_price": avgFillPrice,
                "parent_id": parentId,
                "permanent_id": permId,
            }
        )
        if status in {"PreSubmitted", "Submitted", "Filled", "Cancelled", "ApiCancelled", "Inactive"}:
            self.order_complete.set()
        if status in {"Cancelled", "ApiCancelled"}:
            self.cancel_complete.set()


def _order(
    *, action: str, quantity: int, order_type: str, account: str, tif: str,
    parent_id: int = 0, transmit: bool = False, limit_price: float | None = None,
    auxiliary_price: float | None = None,
) -> Order:
    order = Order()
    order.action = action
    order.totalQuantity = Decimal(quantity)
    order.orderType = order_type
    order.account = account
    order.tif = tif
    order.parentId = parent_id
    order.transmit = transmit
    if limit_price is not None:
        order.lmtPrice = limit_price
    if auxiliary_price is not None:
        order.auxPrice = auxiliary_price
    return order


def build_bracket_orders(
    request: BracketOrderRequest, *, account: str, parent_order_id: int, transmit: bool
) -> list[tuple[int, Order]]:
    """Build an attached entry/target/stop bracket using consecutive IDs."""
    request.validate()
    side = request.side.upper()
    exit_side = "SELL" if side == "BUY" else "BUY"
    tif = request.time_in_force.upper()
    parent = _order(
        action=side, quantity=request.quantity, order_type=request.entry_type.upper(),
        account=account, tif=tif, transmit=False,
        limit_price=request.limit_price if request.entry_type.upper() == "LMT" else None,
    )
    target = _order(
        action=exit_side, quantity=request.quantity, order_type="LMT", account=account,
        tif=tif, parent_id=parent_order_id, transmit=False, limit_price=request.target_price,
    )
    stop = _order(
        action=exit_side, quantity=request.quantity, order_type="STP", account=account,
        tif=tif, parent_id=parent_order_id, transmit=transmit, auxiliary_price=request.stop_price,
    )
    return [(parent_order_id, parent), (parent_order_id + 1, target), (parent_order_id + 2, stop)]


class PaperBroker:
    """Short-lived connection that refuses anything except a verified paper account."""

    def __init__(
        self, *, expected_account: str, host: str = "127.0.0.1", port: int = 7497,
        client_id: int = 71, timeout: float = 15.0,
    ) -> None:
        if port != 7497:
            raise PaperExecutionError("paper execution is locked to TWS paper port 7497")
        if not expected_account.upper().startswith("DU"):
            raise PaperExecutionError("expected_account must be an IBKR paper account beginning with DU")
        self.expected_account = expected_account
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout

    def _connect(self) -> tuple[_PaperClient, threading.Thread]:
        app = _PaperClient()
        app.connect(self.host, self.port, self.client_id)
        thread = threading.Thread(target=app.run, name="ibkr-paper-execution", daemon=True)
        thread.start()
        if not app.connected.wait(self.timeout) or not app.accounts_received.wait(self.timeout):
            app.disconnect()
            raise PaperExecutionError("IBKR paper connection did not complete before timeout")
        if self.expected_account not in app.accounts:
            app.disconnect()
            raise PaperExecutionError(
                f"connected accounts {app.accounts!r} do not contain expected paper account {self.expected_account!r}"
            )
        if any(not account.upper().startswith("DU") for account in app.accounts):
            app.disconnect()
            raise PaperExecutionError("connection exposes a non-paper account; refusing execution")
        return app, thread

    @staticmethod
    def _disconnect(app: _PaperClient, thread: threading.Thread) -> None:
        if app.isConnected():
            app.disconnect()
        thread.join(timeout=1)

    def place_bracket(self, request: BracketOrderRequest, *, transmit: bool = False) -> dict[str, Any]:
        request.validate()
        if not transmit:
            return {
                "mode": "preview",
                "account": self.expected_account,
                "request": asdict(request),
                "message": "No order was sent. Pass transmit=True only after reviewing this preview.",
            }
        app, thread = self._connect()
        try:
            assert app.next_order_id is not None
            contract = us_etf_contract(request.symbol, "ARCA")
            orders = build_bracket_orders(
                request, account=self.expected_account, parent_order_id=app.next_order_id, transmit=True
            )
            for order_id, order in orders:
                app.placeOrder(order_id, contract, order)
            if not app.order_complete.wait(self.timeout):
                raise PaperExecutionError("IBKR did not acknowledge the bracket before timeout")
            if app.errors:
                raise PaperExecutionError("; ".join(app.errors))
            return {
                "mode": "paper_transmitted",
                "account": self.expected_account,
                "order_ids": [order_id for order_id, _ in orders],
                "events": app.order_events,
            }
        finally:
            self._disconnect(app, thread)

    def cancel_order(self, order_id: int) -> dict[str, Any]:
        if order_id < 1:
            raise PaperExecutionError("order_id must be positive")
        app, thread = self._connect()
        try:
            app.cancelOrder(order_id, "")
            if not app.cancel_complete.wait(self.timeout):
                raise PaperExecutionError("IBKR did not acknowledge cancellation before timeout")
            if app.errors:
                raise PaperExecutionError("; ".join(app.errors))
            return {
                "mode": "paper_cancel",
                "account": self.expected_account,
                "order_id": order_id,
                "events": app.order_events,
            }
        finally:
            self._disconnect(app, thread)
