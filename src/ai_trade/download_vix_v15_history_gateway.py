"""IB Gateway compatibility entry point for the read-only VIX history cache."""

from __future__ import annotations

from ai_trade import market_data
from ai_trade.download_vix_v15_history import main


_original_error = market_data._HistoricalDataClient.error


def _gateway_error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson="") -> None:  # noqa: N802
    # IBKR 2107 is a normal connection-status notice for an on-demand historical
    # data farm; it is not a failed historical request.
    if errorCode == 2107:
        return
    _original_error(self, reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)


market_data._HistoricalDataClient.error = _gateway_error


if __name__ == "__main__":
    raise SystemExit(main())
