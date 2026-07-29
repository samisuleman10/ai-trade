"""Read-only historical-bar downloads from Interactive Brokers."""

from __future__ import annotations

import csv
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


class HistoricalDataError(RuntimeError):
    """Raised when IBKR cannot supply the requested historical bars."""


@dataclass(frozen=True)
class OHLCVBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class _HistoricalDataClient(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.connected = threading.Event()
        self.complete = threading.Event()
        self.errors: list[str] = []
        self.bars: list[OHLCVBar] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.connected.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
        if errorCode not in {2104, 2106, 2158}:
            self.errors.append(f"IBKR {errorCode} (request {reqId}): {errorString}")

    def historicalData(self, reqId: int, bar) -> None:  # noqa: N802
        timestamp = datetime.fromtimestamp(int(str(bar.date)), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.bars.append(
            OHLCVBar(
                timestamp=timestamp,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=float(bar.volume),
            )
        )

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
        self.complete.set()


def us_etf_contract(symbol: str, primary_exchange: str) -> Contract:
    """Return a SMART-routed US ETF contract for read-only market-data research."""
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.primaryExchange = primary_exchange.upper()
    contract.currency = "USD"
    return contract


def spy_contract() -> Contract:
    """Return the SMART-routed SPY ETF contract used for data and paper trading."""
    return us_etf_contract("SPY", "ARCA")


def mgc_continuous_contract() -> Contract:
    """Return the research-only continuous Micro Gold futures contract.

    ``CONTFUT`` is intentionally limited to historical research. It must never
    be passed to an order API; a future execution adapter will select and roll a
    concrete MGC expiry instead.
    """
    contract = Contract()
    contract.symbol = "MGC"
    contract.secType = "CONTFUT"
    contract.exchange = "COMEX"
    contract.currency = "USD"
    return contract


def fx_contract(base: str, quote: str = "USD") -> Contract:
    """Return a research-only IDEALPRO spot-FX contract.

    Spot FX serves MIDPOINT bars only (no TRADES, no volume). Like the
    other contract helpers this is for read-only historical research and
    must never be passed to an order API.
    """
    contract = Contract()
    contract.symbol = base.upper()
    contract.secType = "CASH"
    contract.exchange = "IDEALPRO"
    contract.currency = quote.upper()
    return contract


def fetch_historical_bars(
    *,
    contract: Contract,
    duration: str,
    bar_size: str,
    host: str = "127.0.0.1",
    port: int = 7497,
    client_id: int = 31,
    use_rth: bool = True,
    timeout: float = 30.0,
    end_date_time: str = "",
    what_to_show: str = "TRADES",
) -> list[OHLCVBar]:
    """Fetch completed historical trade bars and disconnect.

    This makes a read-only ``reqHistoricalData`` request. Availability depends
    on the account's market-data entitlement and IBKR pacing/retention limits.
    """
    app = _HistoricalDataClient()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-historical-data", daemon=True)
    thread.start()
    try:
        if not app.connected.wait(timeout):
            detail = "; ".join(app.errors) or "No nextValidId callback received."
            raise HistoricalDataError(f"Could not connect to IBKR at {host}:{port}. {detail}")

        app.reqHistoricalData(
            1,
            contract,
            end_date_time,
            duration,
            bar_size,
            what_to_show,
            1 if use_rth else 0,
            2,
            False,
            [],
        )
        if not app.complete.wait(timeout):
            detail = "; ".join(app.errors) or "Historical-data response did not complete."
            raise HistoricalDataError(detail)
        if app.errors:
            raise HistoricalDataError("; ".join(app.errors))
        if not app.bars:
            raise HistoricalDataError("IBKR returned no historical bars.")
        return app.bars
    finally:
        if app.isConnected():
            app.cancelHistoricalData(1)
            app.disconnect()
        thread.join(timeout=1)


def validate_bars(bars: Iterable[OHLCVBar]) -> dict[str, object]:
    """Return a compact validation report without changing the data."""
    rows = list(bars)
    duplicate_timestamps = len(rows) - len({bar.timestamp for bar in rows})
    invalid_ohlc = [
        bar.timestamp
        for bar in rows
        if bar.low > min(bar.open, bar.close)
        or bar.high < max(bar.open, bar.close)
        or bar.low > bar.high
        or min(bar.open, bar.high, bar.low, bar.close) <= 0
    ]
    ordered = all(left.timestamp < right.timestamp for left, right in zip(rows, rows[1:]))
    return {
        "bar_count": len(rows),
        "first_timestamp": rows[0].timestamp if rows else None,
        "last_timestamp": rows[-1].timestamp if rows else None,
        "duplicate_timestamps": duplicate_timestamps,
        "invalid_ohlc_timestamps": invalid_ohlc,
        "strictly_ordered": ordered,
        "valid": bool(rows) and not duplicate_timestamps and not invalid_ohlc and ordered,
    }


def save_bars(
    bars: Iterable[OHLCVBar], *, directory: Path, symbol: str, timeframe: str, source: str = "ibkr"
) -> tuple[Path, Path]:
    """Save bars and their validation report as local, ignored research data."""
    import json

    rows = list(bars)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / f"{symbol.lower()}_{timeframe}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(bar) for bar in rows)

    validation = validate_bars(rows)
    report = {
        "source": source,
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp_timezone": "UTC",
        "timestamp_format": "ISO 8601 UTC, requested from IBKR as epoch timestamps",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "validation": validation,
    }
    report_path = directory / f"{symbol.lower()}_{timeframe}.validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return csv_path, report_path
