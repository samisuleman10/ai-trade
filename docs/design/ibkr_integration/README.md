# IBKR Connection and Paper-Execution Design

## 1. Purpose

This folder documents the project's Interactive Brokers integration. The design
keeps two broker sessions separate:

| Session | Default port | Authority |
|---|---:|---|
| Real IBKR account | 7496 | Read-only account, position, and market-data access |
| IBKR paper account | 7497 | Read access plus explicitly enabled paper-order operations |

The paper code refuses port `7496`. A paper write also requires an account ID
beginning with `DU` and verifies that the exact account is exposed by the
connected TWS or IB Gateway session.

## 2. Library and protocol

The project uses the official Python `ibapi` package declared in
`pyproject.toml`:

```toml
dependencies = ["ibapi>=9.81.1"]
```

`ibapi` connects over the local TWS/IB Gateway socket. It uses an asynchronous
callback model:

- `EClient` sends requests such as `reqPositions`, `reqOpenOrders`,
  `reqExecutions`, `placeOrder`, and `cancelOrder`.
- `EWrapper` receives account, position, order, execution, error, and completion
  callbacks.
- Each adapter runs the IBKR message loop in a short-lived background thread and
  uses `threading.Event` objects to wait for bounded completion.
- The client disconnects after completing each command.

No web API, credential file, or third-party IBKR wrapper is used.

## 3. Source layout

| File | Responsibility |
|---|---|
| `src/ai_trade/ibkr.py` | Read-only account summaries and position snapshots |
| `src/ai_trade/market_data.py` | Read-only historical OHLCV requests |
| `src/ai_trade/ibkr_paper.py` | Paper-only attached bracket construction, submission, and cancellation |
| `src/ai_trade/paper_order.py` | Bracket-order CLI |
| `src/ai_trade/ibkr_paper_operations.py` | Paper positions, open orders, executions, standalone orders, modification, cancellation, and position closing |
| `src/ai_trade/paper_account.py` | General paper-account operations CLI |

## 4. TWS configuration

### Real account

1. Sign in to the real account in TWS or IB Gateway.
2. Enable socket API clients.
3. Use port `7496`.
4. Keep **Read-Only API** enabled.
5. Use the existing portfolio and market-data commands only.

### Paper account

1. Sign in to Paper Trading in TWS or IB Gateway.
2. Enable socket API clients.
3. Use port `7497`.
4. Disable **Read-Only API** for the paper session.
5. Find the paper account ID, normally in the form `DU…`.
6. Pass that exact ID through `--account`.

Use a stable client ID, default `71`, for the project's paper orders. IBKR order
ownership matters: the safe modify/cancel implementation acts on orders returned
by `reqOpenOrders`, which are orders owned by the same API client ID.

## 5. Safety model

Paper writes require all of these conditions:

1. The configured port equals `7497`.
2. The expected account begins with `DU`.
3. TWS reports the exact expected account through `managedAccounts`.
4. The session exposes no non-`DU` account.
5. The requested operation passes local validation.
6. A mutating CLI command includes `--transmit`.

Without `--transmit`, place, modify, cancel, cancel-all, close, and bracket
commands return a preview and make no write request.

The paper adapters have no code path accepting live port `7496`. The shadow
runner remains disconnected from paper execution, so strategy signals cannot
automatically become orders.

## 6. Supported operations

### Read

- Account summaries and positions
- Historical market data
- Current paper positions
- Open API-owned paper orders
- Paper executions/fills visible to the session
- Submission status callbacks

### Create

- Standalone market orders
- Standalone limit orders
- Attached entry/take-profit/stop brackets

### Update

- Quantity of an open API-owned order
- Limit price of an open API-owned limit order

IBKR modifications resubmit the same order ID with the updated `Order` object.
The adapter first retrieves the original order and contract; it does not rebuild
an unknown live order from incomplete command-line input.

### Cancel/delete

IBKR does not delete broker history. “Delete” means cancelling an open order.
The adapter supports cancelling one API-owned order or all orders owned by the
configured API client ID.

### Close

The close operation reads the actual paper position and submits an opposite-side
market order for its entire absolute quantity. It requires exactly one matching,
non-zero position for the symbol. Partial closing can be done with a standalone
opposite-side order after the user specifies the intended quantity.

## 7. Commands

Replace `DU123456` with the actual paper account.

```powershell
# Read
python -m ai_trade.paper_account --account DU123456 positions
python -m ai_trade.paper_account --account DU123456 orders
python -m ai_trade.paper_account --account DU123456 executions

# Preview and then transmit a standalone limit order
python -m ai_trade.paper_account --account DU123456 place --symbol SPY --side BUY --quantity 1 --order-type LMT --limit-price 500
python -m ai_trade.paper_account --account DU123456 place --symbol SPY --side BUY --quantity 1 --order-type LMT --limit-price 500 --transmit

# Preview and transmit a modification
python -m ai_trade.paper_account --account DU123456 modify --order-id 100 --limit-price 499 --quantity 2
python -m ai_trade.paper_account --account DU123456 modify --order-id 100 --limit-price 499 --quantity 2 --transmit

# Preview and transmit cancellation
python -m ai_trade.paper_account --account DU123456 cancel --order-id 100
python -m ai_trade.paper_account --account DU123456 cancel --order-id 100 --transmit

# Cancel every open order owned by client ID 71
python -m ai_trade.paper_account --account DU123456 cancel-all
python -m ai_trade.paper_account --account DU123456 cancel-all --transmit

# Preview and close an entire position at market
python -m ai_trade.paper_account --account DU123456 close --symbol SPY
python -m ai_trade.paper_account --account DU123456 close --symbol SPY --transmit

# Attached bracket
python -m ai_trade.paper_order --account DU123456 bracket --symbol SPY --quantity 1 --side BUY --entry-type LMT --limit-price 500 --stop-price 495 --target-price 510
python -m ai_trade.paper_order --account DU123456 bracket --symbol SPY --quantity 1 --side BUY --entry-type LMT --limit-price 500 --stop-price 495 --target-price 510 --transmit
```

## 8. Operational limitations

- The ETF contract helper uses SMART routing and ARCA as primary exchange. Other
  asset classes require explicit, reviewed contract builders.
- Modify/cancel is deliberately limited to orders owned by the same API client
  ID. Manual TWS orders and orders from another client ID are visible only under
  different IBKR binding rules and are not modified implicitly.
- A successful API acknowledgement is not the same as a fill. Read executions
  and positions to reconcile final state.
- Market orders can fill at an unexpected simulated price. Preview remains the
  default even though this is a paper account.
- The implementation does not connect the strategy scheduler to execution.
  Automated paper trading requires a separate risk gateway, idempotency store,
  reconciliation loop, loss limits, and kill switch.

## 9. Verification

Unit tests cover live-port rejection, non-paper account rejection, preview
defaults, bracket transmission flags, and input validation:

```powershell
python -m pytest tests/test_ibkr.py tests/test_ibkr_paper.py tests/test_ibkr_paper_operations.py
```

An integration check must be performed with Paper TWS running. Begin with read
commands, then preview a one-share limit order far from the market, transmit it,
confirm it appears in `orders`, modify it, cancel it, and confirm cancellation.
