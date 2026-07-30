"""Full paper-account operations, isolated from the live read-only IBKR path."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import ExecutionFilter
from ibapi.order import Order
from ibapi.wrapper import EWrapper

from ai_trade.ibkr_paper import PaperExecutionError
from ai_trade.market_data import us_etf_contract


TERMINAL_STATUSES = {"Filled", "Cancelled", "ApiCancelled", "Inactive"}
ACKNOWLEDGED_STATUSES = TERMINAL_STATUSES | {"PreSubmitted", "Submitted"}


@dataclass(frozen=True)
class PaperOrderRequest:
    symbol: str
    side: str
    quantity: int
    order_type: str = "LMT"
    limit_price: float | None = None
    time_in_force: str = "DAY"

    def validate(self) -> None:
        if self.side.upper() not in {"BUY", "SELL"}:
            raise PaperExecutionError("side must be BUY or SELL")
        if self.quantity <= 0:
            raise PaperExecutionError("quantity must be a positive whole number")
        if self.order_type.upper() not in {"MKT", "LMT"}:
            raise PaperExecutionError("order_type must be MKT or LMT")
        if self.order_type.upper() == "LMT" and (self.limit_price is None or self.limit_price <= 0):
            raise PaperExecutionError("a positive limit_price is required for LMT")
        if self.time_in_force.upper() not in {"DAY", "GTC"}:
            raise PaperExecutionError("time_in_force must be DAY or GTC")


class _OperationsClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.accounts_complete = threading.Event()
        self.open_orders_complete = threading.Event()
        self.executions_complete = threading.Event()
        self.positions_complete = threading.Event()
        self.order_event = threading.Event()
        self.accounts: list[str] = []
        self.next_order_id: int | None = None
        self.errors: list[str] = []
        self.open_orders: dict[int, tuple[Contract, Order, str]] = {}
        self.executions: list[dict[str, Any]] = []
        self.positions: list[tuple[Contract, Decimal, float, str]] = []
        self.statuses: list[dict[str, Any]] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_order_id = orderId
        self.connected.set()

    def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
        self.accounts = [item.strip() for item in accountsList.split(",") if item.strip()]
        self.accounts_complete.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        if errorCode not in {2104, 2106, 2107, 2108, 2158}:
            message = f"IBKR {errorCode} (request {reqId}): {errorString}"
            if advancedOrderRejectJson:
                message += f" reject={advancedOrderRejectJson}"
            self.errors.append(message)
            self.order_event.set()

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState) -> None:  # noqa: N802
        self.open_orders[orderId] = (contract, order, orderState.status)

    def openOrderEnd(self) -> None:  # noqa: N802
        self.open_orders_complete.set()

    def execDetails(self, reqId: int, contract: Contract, execution) -> None:  # noqa: N802
        self.executions.append(
            {
                "execution_id": execution.execId,
                "order_id": execution.orderId,
                "permanent_id": execution.permId,
                "account": execution.acctNumber,
                "symbol": contract.symbol,
                "security_type": contract.secType,
                "side": execution.side,
                "shares": str(execution.shares),
                "price": execution.price,
                "time": execution.time,
            }
        )

    def execDetailsEnd(self, reqId: int) -> None:  # noqa: N802
        self.executions_complete.set()

    def position(self, account: str, contract: Contract, position: Decimal, avgCost: float) -> None:  # noqa: N802
        self.positions.append((contract, position, avgCost, account))

    def positionEnd(self) -> None:  # noqa: N802
        self.positions_complete.set()

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
                "parent_id": parentId,
            }
        )
        if status in ACKNOWLEDGED_STATUSES:
            self.order_event.set()


def _public_order(order_id: int, contract: Contract, order: Order, status: str) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "symbol": contract.symbol,
        "security_type": contract.secType,
        "action": order.action,
        "quantity": str(order.totalQuantity),
        "order_type": order.orderType,
        "limit_price": order.lmtPrice if order.orderType == "LMT" else None,
        "auxiliary_price": order.auxPrice if order.orderType in {"STP", "STP LMT"} else None,
        "time_in_force": order.tif,
        "parent_id": order.parentId,
        "status": status,
        "account": order.account,
    }


class PaperAccountOperations:
    """Paper-only broker operations locked to port 7497 and a specific DU account."""

    def __init__(
        self, *, expected_account: str, host: str = "127.0.0.1", port: int = 7497,
        client_id: int = 71, timeout: float = 15.0,
    ) -> None:
        if port != 7497:
            raise PaperExecutionError("paper operations are locked to TWS paper port 7497")
        if not expected_account.upper().startswith("DU"):
            raise PaperExecutionError("expected_account must be an IBKR paper account beginning with DU")
        self.account = expected_account
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout

    def _connect(self) -> tuple[_OperationsClient, threading.Thread]:
        app = _OperationsClient()
        app.connect(self.host, self.port, self.client_id)
        thread = threading.Thread(target=app.run, name="ibkr-paper-operations", daemon=True)
        thread.start()
        if not app.connected.wait(self.timeout) or not app.accounts_complete.wait(self.timeout):
            app.disconnect()
            raise PaperExecutionError("IBKR paper connection did not complete before timeout")
        if self.account not in app.accounts:
            app.disconnect()
            raise PaperExecutionError(f"expected paper account {self.account!r} not found in {app.accounts!r}")
        if any(not value.upper().startswith("DU") for value in app.accounts):
            app.disconnect()
            raise PaperExecutionError("connection exposes a non-paper account; refusing all writes")
        return app, thread

    @staticmethod
    def _disconnect(app: _OperationsClient, thread: threading.Thread) -> None:
        if app.isConnected():
            app.disconnect()
        thread.join(timeout=1)

    def _open_orders(self, app: _OperationsClient) -> dict[int, tuple[Contract, Order, str]]:
        app.reqOpenOrders()
        if not app.open_orders_complete.wait(self.timeout):
            raise PaperExecutionError("open-order request timed out")
        if app.errors:
            raise PaperExecutionError("; ".join(app.errors))
        return app.open_orders

    def list_open_orders(self) -> list[dict[str, Any]]:
        app, thread = self._connect()
        try:
            orders = self._open_orders(app)
            return [_public_order(order_id, *value) for order_id, value in sorted(orders.items())]
        finally:
            self._disconnect(app, thread)

    def list_executions(self) -> list[dict[str, Any]]:
        app, thread = self._connect()
        try:
            app.reqExecutions(9001, ExecutionFilter())
            if not app.executions_complete.wait(self.timeout):
                raise PaperExecutionError("execution request timed out")
            if app.errors:
                raise PaperExecutionError("; ".join(app.errors))
            return app.executions
        finally:
            self._disconnect(app, thread)

    def list_positions(self) -> list[dict[str, Any]]:
        app, thread = self._connect()
        try:
            app.reqPositions()
            if not app.positions_complete.wait(self.timeout):
                raise PaperExecutionError("position request timed out")
            return [
                {
                    "account": account,
                    "symbol": contract.symbol,
                    "security_type": contract.secType,
                    "currency": contract.currency,
                    "quantity": str(quantity),
                    "average_cost": average_cost,
                    "con_id": contract.conId,
                }
                for contract, quantity, average_cost, account in app.positions
            ]
        finally:
            app.cancelPositions()
            self._disconnect(app, thread)

    def place_order(self, request: PaperOrderRequest, *, transmit: bool = False) -> dict[str, Any]:
        request.validate()
        if not transmit:
            return {"mode": "preview", "account": self.account, "request": request.__dict__}
        app, thread = self._connect()
        try:
            assert app.next_order_id is not None
            order = Order()
            order.account = self.account
            order.action = request.side.upper()
            order.totalQuantity = Decimal(request.quantity)
            order.orderType = request.order_type.upper()
            order.tif = request.time_in_force.upper()
            order.transmit = True
            if request.limit_price is not None:
                order.lmtPrice = request.limit_price
            app.placeOrder(app.next_order_id, us_etf_contract(request.symbol, "ARCA"), order)
            if not app.order_event.wait(self.timeout) or app.errors:
                raise PaperExecutionError("; ".join(app.errors) or "order acknowledgement timed out")
            return {"mode": "paper_transmitted", "order_id": app.next_order_id, "statuses": app.statuses}
        finally:
            self._disconnect(app, thread)

    def modify_order(
        self, order_id: int, *, quantity: int | None = None,
        limit_price: float | None = None, transmit: bool = False,
    ) -> dict[str, Any]:
        if quantity is not None and quantity <= 0:
            raise PaperExecutionError("quantity must be positive")
        if limit_price is not None and limit_price <= 0:
            raise PaperExecutionError("limit_price must be positive")
        app, thread = self._connect()
        try:
            orders = self._open_orders(app)
            if order_id not in orders:
                raise PaperExecutionError(
                    "order is not an open API order owned by this client_id; it cannot be modified safely"
                )
            contract, order, status = orders[order_id]
            before = _public_order(order_id, contract, order, status)
            if quantity is not None:
                order.totalQuantity = Decimal(quantity)
            if limit_price is not None:
                if order.orderType != "LMT":
                    raise PaperExecutionError("limit_price can only modify an LMT order")
                order.lmtPrice = limit_price
            after = _public_order(order_id, contract, order, status)
            if not transmit:
                return {"mode": "preview_modify", "before": before, "after": after}
            app.order_event.clear()
            app.placeOrder(order_id, contract, order)
            if not app.order_event.wait(self.timeout) or app.errors:
                raise PaperExecutionError("; ".join(app.errors) or "modify acknowledgement timed out")
            return {"mode": "paper_modified", "order_id": order_id, "statuses": app.statuses}
        finally:
            self._disconnect(app, thread)

    def cancel_order(self, order_id: int, *, transmit: bool = False) -> dict[str, Any]:
        if order_id <= 0:
            raise PaperExecutionError("order_id must be positive")
        if not transmit:
            return {"mode": "preview_cancel", "account": self.account, "order_id": order_id}
        app, thread = self._connect()
        try:
            if order_id not in self._open_orders(app):
                raise PaperExecutionError("order is not an open API order owned by this client_id")
            app.order_event.clear()
            app.cancelOrder(order_id, "")
            if not app.order_event.wait(self.timeout) or app.errors:
                raise PaperExecutionError("; ".join(app.errors) or "cancel acknowledgement timed out")
            return {"mode": "paper_cancelled", "order_id": order_id, "statuses": app.statuses}
        finally:
            self._disconnect(app, thread)

    def cancel_all(self, *, transmit: bool = False) -> dict[str, Any]:
        if not transmit:
            return {"mode": "preview_cancel_all", "account": self.account}
        app, thread = self._connect()
        try:
            owned_ids = sorted(self._open_orders(app))
            for order_id in owned_ids:
                app.cancelOrder(order_id, "")
            return {"mode": "paper_cancel_all_requested", "order_ids": owned_ids}
        finally:
            self._disconnect(app, thread)

    def close_position(self, symbol: str, *, transmit: bool = False) -> dict[str, Any]:
        app, thread = self._connect()
        try:
            app.reqPositions()
            if not app.positions_complete.wait(self.timeout):
                raise PaperExecutionError("position request timed out")
            matches = [
                item for item in app.positions
                if item[3] == self.account and item[0].symbol.upper() == symbol.upper() and item[1] != 0
            ]
            if len(matches) != 1:
                raise PaperExecutionError(f"expected exactly one non-zero {symbol} paper position, found {len(matches)}")
            contract, quantity, _, _ = matches[0]
            preview = {
                "symbol": contract.symbol,
                "side": "SELL" if quantity > 0 else "BUY",
                "quantity": str(abs(quantity)),
                "order_type": "MKT",
            }
            if not transmit:
                return {"mode": "preview_close", "account": self.account, "order": preview}
            assert app.next_order_id is not None
            order = Order()
            order.account = self.account
            order.action = preview["side"]
            order.totalQuantity = abs(quantity)
            order.orderType = "MKT"
            order.tif = "DAY"
            order.transmit = True
            app.placeOrder(app.next_order_id, contract, order)
            if not app.order_event.wait(self.timeout) or app.errors:
                raise PaperExecutionError("; ".join(app.errors) or "close acknowledgement timed out")
            return {"mode": "paper_close_transmitted", "order_id": app.next_order_id, "statuses": app.statuses}
        finally:
            app.cancelPositions()
            self._disconnect(app, thread)
