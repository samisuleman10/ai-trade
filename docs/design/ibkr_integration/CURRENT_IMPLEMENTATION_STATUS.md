# IBKR Integration — Current Implementation Status

**Status date:** 23 July 2026  
**Environment:** Windows, local TWS/IB Gateway socket API  
**Python library:** Official `ibapi` package, version constraint `ibapi>=9.81.1`

## 1. Executive summary

The project now has two operationally separate IBKR connections:

| Environment | Application | Host | Port | Authority | Verified |
|---|---|---:|---:|---|---|
| Real account | IB Gateway | `localhost` | `4001` | Read-only | Yes |
| Paper account | Trader Workstation | `localhost` | `7497` | Read and paper execution | Yes |

The real-account connection is used for account data, historical bars, and
quotes. Its API remains read-only. The paper connection can read account state
and submit simulated orders after explicit transmission is requested.

The core connection and one end-to-end paper market order are verified.
Production-quality automated paper trading is not yet complete because the
remaining order types, persistent reconciliation, and portfolio risk controls
still require integration testing and consolidation.

## 2. Verified real-account functionality

### Connection

- IB Gateway listens locally on port `4001`.
- The project connects using `host="localhost"`.
- Account and position synchronization completed successfully.
- The real connection is configured with IBKR's **Read-Only API** option.
- No real order was submitted or attempted.

### Portfolio access

The existing `ai_trade.sync_portfolio` command successfully saved a real-account
snapshot under:

```text
data/portfolio/live/
```

The verified real snapshot contained no open positions at the time of the test.

### Historical and chart data

IB Gateway exposes the same TWS socket API used by the project's historical-bar
downloaders. It can therefore provide the real-account data used for SPY and
other locally rendered charts:

- Historical OHLCV bars
- Completed intraday bars
- Bid, ask, last, high, low, and previous close when permitted
- Live data when the account has the required exchange subscription
- Delayed data when IBKR makes it available without a subscription

IB Gateway itself does not display charts. It supplies data to the project,
which stores, validates, analyzes, and renders the charts locally.

### CALM quote test

A read-only snapshot was requested for Cal-Maine Foods, Inc. (`CALM`) through
the real IB Gateway connection.

IBKR reported that the account did not have the required live NASDAQ API
subscription and automatically supplied delayed data. The returned snapshot was:

| Field | Value |
|---|---:|
| Last | USD 88.61 |
| Bid | USD 88.23 |
| Ask | USD 88.99 |
| Day high | USD 90.06 |
| Day low | USD 87.25 |
| Previous close | USD 87.86 |
| Market-data type | Delayed |
| Request time | 2026-07-23 13:51:40 UTC |

IBKR documents delayed API data as normally 15–20 minutes behind real time;
U.S. equity data is commonly approximately 15 minutes delayed.

## 3. Verified paper-account functionality

### Connection and balance

Paper TWS listens locally on port `7497`. The connection succeeded using
`localhost`; `127.0.0.1` did not connect because the local listener was exposed
through the IPv6 wildcard binding.

The first verified paper snapshot contained:

| Field | Value |
|---|---:|
| Net liquidation | EUR 1,010,832.30 |
| Total cash value | EUR 1,009,840.50 |
| Available funds | EUR 1,010,832.30 |
| Buying power | EUR 6,738,882.00 |
| Excess liquidity | EUR 1,010,832.30 |
| Positions at snapshot time | 0 |

The paper account identifier is deliberately not reproduced in this design
document. Runtime commands require the exact `DU…` identifier.

### Read access

The following paper reads have been verified against the running TWS session:

- Account summary and balances
- Positions
- Open API orders
- Executions/fills
- Order status

### Successful CALM paper execution

An explicitly authorized paper market order was submitted:

| Field | Value |
|---|---|
| Symbol | CALM |
| Action | Buy |
| Quantity | 6 shares |
| Order type | Market |
| Time in force | DAY |
| Initial state | PreSubmitted |
| Final state | Filled |
| Execution price | USD 88.21 |
| Recorded average cost | USD 88.37666965 |
| Execution time reported by IBKR | 2026-07-23 15:30:02 |

After reconciliation:

- Open CALM orders: none
- CALM position: 6 shares
- Execution history contained the completed purchase

No real-account order authority was involved.

## 4. Implemented paper operations

The source currently implements:

### Read

- Account balances and positions
- Open API-owned orders
- Execution/fill history
- Historical bars
- Order status callbacks

### Create

- Standalone market orders
- Standalone limit orders
- Parent entry orders
- Attached take-profit limit orders
- Attached stop-loss orders
- Three-part bracket submission

### Update

- Modify the total quantity of an open API-owned order
- Modify the price of an open API-owned limit order
- Resubmit the same IBKR order ID and original contract

### Cancel

- Cancel one open API-owned order
- Request cancellation of all orders owned by the configured API client ID

IBKR retains order history; “delete” means cancelling an open order.

### Close

- Read the actual paper position
- Verify there is exactly one matching non-zero position
- Submit an opposite-side market order for the entire absolute quantity

Partial closing is possible through an explicitly sized standalone opposite-side
order, but the dedicated close command intentionally closes the whole position.

## 5. Safety controls

Paper-write code applies independent checks:

1. Paper operations accept only port `7497`.
2. The expected account ID must begin with `DU`.
3. TWS must report the exact expected paper account.
4. A connection exposing any non-paper account is rejected.
5. Order side, quantity, type, and prices are validated locally.
6. Mutating CLI commands default to preview mode.
7. `--transmit` is required before a write request is sent.
8. The real port `7496` is rejected by the paper adapters.
9. Real IB Gateway port `4001` is not accepted by paper execution code.
10. The strategy and shadow runners are not connected to order execution.

Modification and cancellation are deliberately limited to orders returned by
`reqOpenOrders` for the same API client ID. Orders created manually in TWS or by
another API client are not modified implicitly.

## 6. TWS API compatibility finding

The declared official package version, `ibapi 9.81.1.post1`, creates legacy
`EtradeOnly` and `firmQuoteOnly` order attributes by default. Current TWS
rejected the first CALM request with error `10268`:

```text
The 'EtradeOnly' order attribute is not supported.
```

The request was rejected before acceptance, so it created no order.

The compatibility submission path explicitly sets both legacy attributes to
`False`. After that adjustment, the same authorized CALM paper order was
accepted and filled successfully.

This compatibility handling currently exists in:

```text
src/ai_trade/ibkr_paper_compat_order.py
```

Before all order types are declared fully verified, the same handling must be
consolidated into the main order factory used by standalone, bracket, modify,
and position-close operations.

## 7. Quote compatibility finding

IBKR returns different tick IDs for delayed market data:

- Live bid/ask/last: tick IDs 1, 2, and 4
- Delayed bid/ask/last: tick IDs 66, 67, and 68
- Delayed high/low/close: tick IDs 72, 73, and 75

The first quote helper recognized live identifiers only. Gateway correctly
reported delayed availability, but the helper initially returned no prices.
The delayed-capable Gateway helper maps both live and delayed tick identifiers:

```text
src/ai_trade/ibkr_gateway_quote.py
```

This helper successfully returned the CALM delayed snapshot documented above.

## 8. Source files

| File | Purpose |
|---|---|
| `src/ai_trade/ibkr.py` | Read-only account summaries and portfolio snapshots |
| `src/ai_trade/market_data.py` | Read-only historical OHLCV data |
| `src/ai_trade/ibkr_quote.py` | Initial one-time quote implementation |
| `src/ai_trade/ibkr_delayed_quote.py` | Intermediate delayed-data compatibility helper |
| `src/ai_trade/ibkr_gateway_quote.py` | Verified live/delayed Gateway quote mapping |
| `src/ai_trade/ibkr_paper.py` | Paper bracket-order model and initial adapter |
| `src/ai_trade/paper_order.py` | Paper bracket CLI |
| `src/ai_trade/ibkr_paper_operations.py` | Paper account operations |
| `src/ai_trade/paper_account.py` | General paper-operations CLI |
| `src/ai_trade/ibkr_paper_compat_order.py` | Current-TWS compatible verified market-order path |

## 9. Test status

The project-local `.venv` was created and the declared dependencies installed.

The focused IBKR unit suite completed successfully:

```text
11 passed
```

Covered behavior includes:

- Rejection of live port `7496`
- Rejection of non-paper account IDs
- Preview mode without a connection or transmission
- Bracket parent/child order IDs
- Bracket transmission flags
- Price-order validation
- Cancellation preview defaults
- Existing read-only snapshot serialization

The CALM order additionally provided an end-to-end integration test for:

- Paper connection
- Account verification
- Current-TWS order serialization
- Market-order acceptance
- Status receipt
- Fill reconciliation
- Position reconciliation

## 10. Implemented but not yet fully integration-tested

These capabilities exist in code but have not all completed a small live paper
test against the currently running TWS version:

- Standalone limit-order submission
- Bracket submission
- Stop-loss child activation
- Take-profit child activation
- Limit-order price modification
- Quantity modification
- Single-order cancellation
- Cancel-all
- Whole-position closing
- Behavior across a TWS disconnect/restart

Until those tests pass, only the compatible standalone paper market-order path
should be described as end-to-end verified.

## 11. Remaining work before automated paper trading

### Adapter consolidation

- Move the verified legacy-attribute compatibility handling into one shared
  order factory.
- Replace the intermediate quote helpers with one canonical quote adapter.
- Add contract builders with explicit primary exchanges instead of assuming all
  U.S. equities use the same primary exchange.
- Add one consistent result and error schema.

### Persistent order lifecycle

- Store order intents before broker submission.
- Record the IBKR order ID and permanent ID.
- Persist acknowledgements, partial fills, fills, rejections, and cancellations.
- Reconcile open orders, executions, and positions after every restart.
- Prevent duplicate submission using a durable idempotency key.
- Detect orders and positions that exist at IBKR but not in local records.

### Risk controls

- Maximum order quantity and notional value
- Maximum position size per symbol
- Maximum total portfolio exposure
- Maximum daily realized and unrealized loss
- Maximum number of open orders
- Price and spread sanity checks
- Market-hours and stale-data checks
- Manual kill switch
- Automatic cancellation of working strategy orders after a risk breach
- Rejection of orders when broker state cannot be reconciled

### Operational controls

- Structured audit log
- Persistent execution database or append-only event log
- Alerts for rejection, partial fill, disconnect, and reconciliation mismatch
- Heartbeat and connection-health monitoring
- Controlled reconnect behavior
- Daily paper-account report

### Integration tests

Use one-share paper orders where possible:

1. Submit a limit order away from the market.
2. Verify it appears in open orders.
3. Modify its price and quantity.
4. Cancel it and verify terminal state.
5. Submit a bracket with a non-marketable parent.
6. Verify both child relationships and transmit flags.
7. Cancel the bracket.
8. Open a small position.
9. Close it through the dedicated close command.
10. Restart TWS and verify complete reconciliation.

## 12. Current readiness statement

The system is ready for:

- Read-only real-account portfolio and market-data use
- Real historical-data collection for local charts and research
- Delayed real-account quote snapshots where subscriptions are absent
- Manual, explicitly authorized paper market orders through the verified
  compatibility path
- Paper account, order, execution, and position inspection

The system is not yet ready for:

- Automated strategy-to-order submission
- Unattended paper execution
- Production or live-money order execution
- Claiming all order-management functions are fully verified

Real-account execution remains outside the approved architecture.
