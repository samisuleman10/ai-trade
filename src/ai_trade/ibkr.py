"""Read-only portfolio snapshots from IBKR TWS or IB Gateway."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


class IBKRSyncError(RuntimeError):
    """Raised when IBKR cannot supply a complete portfolio snapshot."""


@dataclass(frozen=True)
class Position:
    account: str
    symbol: str
    security_type: str
    currency: str
    exchange: str
    quantity: str
    average_cost: float
    con_id: int


class _PortfolioClient(EWrapper, EClient):
    """Collects the one-time responses to IBKR's account and positions requests."""

    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.summary_complete = threading.Event()
        self.positions_complete = threading.Event()
        self.errors: list[str] = []
        self.summary: dict[str, dict[str, dict[str, str]]] = {}
        self.positions: list[Position] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBKR callback name
        self.connected.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        # 2104/2106/2158 are routine market-data status messages, unrelated to this read-only sync.
        if errorCode not in {2104, 2106, 2158}:
            self.errors.append(f"IBKR {errorCode} (request {reqId}): {errorString}")

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:  # noqa: N802
        self.summary.setdefault(account, {})[tag] = {"value": value, "currency": currency}

    def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802
        self.summary_complete.set()

    def position(self, account: str, contract: Contract, position: Decimal, avgCost: float) -> None:  # noqa: N802
        self.positions.append(
            Position(
                account=account,
                symbol=contract.symbol,
                security_type=contract.secType,
                currency=contract.currency,
                exchange=contract.exchange,
                quantity=str(position),
                average_cost=avgCost,
                con_id=contract.conId,
            )
        )

    def positionEnd(self) -> None:  # noqa: N802
        self.positions_complete.set()


def fetch_portfolio(host: str = "127.0.0.1", port: int = 7497, client_id: int = 17, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch balances and positions, then disconnect immediately.

    TWS paper trading commonly uses port 7497; live TWS commonly uses 7496.
    The function makes no order, market-data, or account-changing request.
    """
    app = _PortfolioClient()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-api", daemon=True)
    thread.start()
    try:
        if not app.connected.wait(timeout):
            detail = "; ".join(app.errors) or "No nextValidId callback received."
            raise IBKRSyncError(f"Could not connect to IBKR at {host}:{port}. {detail}")

        app.reqAccountSummary(1, "All", "NetLiquidation,TotalCashValue,BuyingPower,AvailableFunds,ExcessLiquidity")
        app.reqPositions()
        if not app.summary_complete.wait(timeout) or not app.positions_complete.wait(timeout):
            raise IBKRSyncError("IBKR did not complete the portfolio response before timeout.")

        return {
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "source": {"host": host, "port": port, "client_id": client_id},
            "accounts": app.summary,
            "positions": [asdict(position) for position in app.positions],
        }
    finally:
        if app.isConnected():
            app.cancelAccountSummary(1)
            app.cancelPositions()
            app.disconnect()
        thread.join(timeout=1)


def save_snapshot(snapshot: dict[str, Any], directory: Path) -> Path:
    """Write a timestamped JSON snapshot and return its path."""
    import json

    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"portfolio-{stamp}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
