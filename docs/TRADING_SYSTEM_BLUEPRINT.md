# Trading System Blueprint

## End goal

Build a **reliable, measurable automated trading system** that can run a
clearly defined strategy on approved venues (IBKR and MEXC), while preserving
control at every step.

The goal is not simply:

> Make a signal and submit an order.

The goal is the complete, repeatable lifecycle:

```text
Define hypothesis -> collect trustworthy data -> backtest -> paper/shadow trade
-> risk-check -> execute -> reconcile actual fills -> monitor -> evaluate
-> improve or retire the strategy -> repeat
```

The system should make its behaviour auditable: for every order, we must be
able to explain the strategy decision, the risk decision, the order sent, the
fill received, and the eventual outcome.

This is engineering infrastructure, not investment advice or a promise of
profit. A positive backtest is evidence to investigate, not approval to trade.

## What "complete" means

| Capability | What it means |
| --- | --- |
| Strategy | Rules are explicit, versioned, and deterministic. An AI may assist research, but it does not directly place orders. |
| Data | Historical and live market data is collected, validated, timestamped, and stored locally. |
| Backtesting | Tests include realistic commissions, slippage, funding, leverage, and position constraints where relevant. |
| Risk | A venue-independent gateway enforces capital, exposure, loss, leverage, and order-size limits before any order is submitted. |
| Execution | Broker/exchange adapters translate approved intents to IBKR or MEXC orders, handling retries and duplicate prevention. |
| Reconciliation | Actual balances, positions, orders, and fills are repeatedly compared with our internal records. |
| Monitoring | A dashboard and alerts expose health, open risk, P&L, missed data, failed orders, and abnormal behaviour. |
| Improvement | Results are analysed against the original backtest. Strategies are changed only through a new version and a new validation cycle. |

## Target architecture

```text
                      [Strategy definitions]
                           versioned rules
                                 |
Market data --> local data --> backtester / live strategy
 IBKR + MEXC        |                    |
                    |                    v
                    |             approved trade intent
                    |                    |
                    v                    v
          analytics & reports <-- fills / Risk gateway
                                           |
                                           v
                                  execution adapters
                                    IBKR / MEXC
                                           |
                                           v
                             broker truth: orders, positions,
                               balances, and executions
```

The broker/exchange is always the source of truth for money, positions, and
fills. Our system must reconcile with it rather than assume that a submitted
order was filled.

## Operating modes

Every strategy and adapter must declare one mode:

1. **Research** - download data and inspect ideas; no orders.
2. **Backtest** - run deterministic simulations on historical data; no orders.
3. **Shadow** - calculate signals against live prices and log the hypothetical
   trades; no orders.
4. **Paper** - send orders only to a broker/exchange paper environment.
5. **Live** - send limited real orders after explicit approval and proven paper
   performance.

Moving forward is a decision gate, not an automatic promotion. Moving backward
or stopping must always be possible immediately.

## Delivery roadmap

### Phase 0 - Foundation (completed / in progress)

- Read-only IBKR portfolio sync.
- Read-only MEXC spot and futures sync.
- Local secrets in `.env`, excluded from Git.
- MEXC history preserved and an initial trading-history dashboard produced.

### Phase 1 - Trusted historical-data store

- Add candle downloaders for one selected MEXC market and timeframe.
- Save normalized OHLCV data locally with source, symbol, timeframe, and
  collection timestamps.
- Detect gaps, duplicates, time-zone errors, and incomplete candles.
- Define fee, funding, and leverage assumptions for futures tests.

**Exit condition:** the same date range can be downloaded, validated, and used
by a backtest repeatedly.

### Phase 2 - First reproducible strategy and backtest

- Choose one simple, fully rule-based strategy and one market.
- Implement entry, exit, sizing, stop, and no-trade rules in Python.
- Produce a trade ledger, equity curve, drawdown, win rate, profit factor, and
  exposure report.
- Test in-sample and untouched out-of-sample periods; include parameter
  sensitivity checks rather than tuning for the best historical number.

**Exit condition:** results can be reproduced from a strategy version, a data
snapshot, and a configuration file.

### Phase 3 - Live decision loop without orders

- Run the strategy on live data in shadow mode.
- Record intended entries, exits, prices, sizing, and expected costs.
- Compare hypothetical results to the backtest assumptions.
- Add health checks for stale data, connection loss, and missing candles.

**Exit condition:** shadow operation is stable and its behaviour matches the
strategy specification.

### Phase 4 - Risk and paper execution

- Define hard limits: maximum order notional, max position, leverage cap,
  daily loss stop, total exposure, allowed symbols, and allowed trading hours.
- Add an approval/risk gateway between strategy and any broker adapter.
- Implement idempotent order submission, order-state tracking, partial-fill
  handling, cancellation, and reconciliation.
- Enable paper trading only; retain IBKR's live **Read-Only API** setting.

**Exit condition:** paper orders, fills, restarts, and disconnections reconcile
correctly with the venue.

### Phase 5 - Limited live operation

- Require explicit user approval to enable trading permissions and live order
  code.
- Start with a strict, small-capital limit and one strategy/venue.
- Alert on every order, fill, rejected order, disconnection, limit breach, and
  daily stop.
- Provide a manual kill switch that blocks all new orders immediately.

**Exit condition:** live operation remains within limits and continuously
matches broker records.

### Phase 6 - Measurement and improvement

- Compare live, paper, shadow, and backtest results.
- Attribute differences to fees, slippage, fills, timing, funding, or rule
  deviations.
- Maintain a strategy scorecard: return, drawdown, hit rate, profit factor,
  turnover, capacity, and operational incidents.
- Promote changes only as a new version through the same backtest -> shadow ->
  paper validation path.
- Pause or retire strategies when their assumptions no longer hold.

## Safety rules

- No secrets in source code, dashboards, logs, or Git.
- No withdrawal permission on exchange keys used by the system.
- No live trade is placed directly by an LLM or chat instruction.
- A strategy produces an **intent**; the risk gateway decides whether it may be
  sent.
- Start with one strategy, one venue, and a small constrained scope.
- Do not disable IBKR Read-Only API or grant MEXC trade permission until Phase
  4 is complete and the user explicitly authorizes that change.
- Every live order needs a durable client order ID and a matching audit record.

## Immediate next decision

Select the first narrow experiment:

```text
Venue: MEXC spot or MEXC futures
Market: one symbol
Timeframe: one candle interval
Strategy: one simple rule set
Mode: backtest only
```

Once those four choices are made, Phase 1 and Phase 2 can be implemented
without enabling trading permissions.
