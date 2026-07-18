---
id: strategy_01_v3_shadow_trading_specification
title: Strategy 01 v3 Shadow-Trading Specification
status: approved_for_build
execution_authority: no_broker_orders
owner: Sami
last_updated: 2026-07-16
---

# Strategy 01 v3: Shadow-Trading Specification

## 1. Purpose

Turn the locked Strategy 01 v3 rules into an automated **shadow-trading loop**.
The system will detect completed signals, calculate a proposed position, monitor
the simulated trade, and produce review data. It will not submit, modify, or
cancel an order at IBKR, MEXC, or any other venue.

The objective is to collect forward-test evidence before any broker-connected
paper trading is considered.

## 2. Scope of the first shadow loop

| Area | v3 shadow decision |
| --- | --- |
| Instrument | SPY only; this is the locked v3 baseline instrument. |
| Direction | Long only while the macro stance is manually `bullish`. |
| Trend / entry | Completed 4-hour Alligator background state; completed 1-hour signal. |
| Signal schedule | Run after each completed regular-session 1-hour bar, Monday–Thursday. |
| Trading windows | Eligible decision bars: 10:30, 11:30, 12:30, 13:30, and 14:30 New York time. |
| Friday | No entry; open shadow trade closes using the documented Friday close rule. |
| Holding | Weeknight holding allowed; no weekend holding. |
| Starting model equity | $100,000, configurable only as a simulation input. |
| Initial risk | 0.15% of current simulated equity. |
| RRMS | Four tiers: 0.15%, 0.35%, 0.70%, 1.50%; reset after a win or after tier 4. |
| Execution | Simulated next-bar entry, simulated stop/target/Friday exit. |
| Broker access | Explicitly prohibited. Read-only market-data retrieval is allowed. |

QQQ, DIA, and MGC results remain research comparisons. They are not in the
first shadow loop.

## 3. End-to-end lifecycle

```text
Manual macro stance
       ↓
Completed-bar market data
       ↓
Strategy v3 signal engine
       ↓
Risk gateway and simulated position sizing
       ↓
Trade-intent ledger (pending / accepted / rejected)
       ↓
Shadow position monitor
       ↓
Exit simulator and reconciled trade ledger
       ↓
Daily review + validation metrics
```

## 4. Signal cycle

At each eligible completed 1-hour bar:

1. Retrieve only completed SPY 1-hour and 4-hour regular-session bars.
2. Record the data timestamp and validation result. Reject the cycle if data is
   stale, incomplete, duplicated, or invalid.
3. Read the manual macro stance from a local configuration record.
4. Apply the locked Strategy 01 v3 filters.
5. If a signal exists, calculate the stop below the Jaw, target at 1R, and
   simulated next-bar entry.
6. Send the proposal to the risk gateway. A rejected proposal is retained with
   its reason; it must not silently disappear.
7. If accepted, create a shadow trade only. No API order method may be called.

## 5. Risk gateway

The gateway must run before every accepted shadow trade and must reject a
proposal if any check fails.

| Check | Initial rule |
| --- | --- |
| Macro stance | Must be `bullish`. |
| Strategy state | One active shadow position maximum for SPY. |
| Session | Must be an approved 1-hour entry window, Monday–Thursday. |
| Stop | Must be below entry for a long trade and below the configured maximum stop distance. |
| Quantity | Whole SPY shares; quantity must be at least one share. |
| Risk | Expected loss at stop, including the modeled cost, may not exceed the active RRMS tier. |
| Daily circuit breaker | Pause new signals after 2 stopped-out trades or 1.0% model-equity realized daily loss. |
| Data integrity | No missing required bar; signal must use completed bars only. |
| Duplicate protection | A decision timestamp may create at most one trade intent. |

The daily circuit breaker is a new safety control for shadow testing. It must
be measured and revisited before any later paper-trading decision.

## 6. Required records

All records are local, append-only CSV or JSON files under ignored `data/` and
`outputs/` folders. They contain no credentials.

| Record | Minimum fields |
| --- | --- |
| Cycle log | run ID, decision timestamp, data timestamps, macro stance, validation status, signal/no-signal reason |
| Trade intent | intent ID, signal values, entry/stop/target, RRMS tier, proposed quantity, gateway decision and rejection reason |
| Shadow trade | intent ID, simulated entry/exit timestamps and prices, exit reason, gross P&L, estimated costs, net P&L, result R, model equity |
| Daily review | date, number of cycles, signals, accepted/rejected intents, open position, realized P&L, risk tier, exceptions |
| Monthly review | sample size, win rate, profit factor, average R, drawdown, exit mix, defects, decision |

Every record must include strategy ID, strategy version, instrument, data source,
and code version or source hash so a result can be reproduced.

## 7. Monitoring and operational behavior

- A scheduler runs only during the defined US regular-session windows.
- An open shadow trade is checked whenever a new completed 1-hour bar arrives.
- Stop/target collision inside a historical bar uses the existing conservative
  assumption: stop is hit before target.
- The Friday close process finalizes any remaining open shadow position before
  the weekend and writes its reason as `weekend_close`.
- If a cycle fails, the system records `data_error` or `system_error`, sends no
  intent, and surfaces the issue in the daily review.
- Restarting the process must rebuild state from the stored ledger without
  generating duplicate intentions or changing a prior trade.

## 8. Validation gates before broker paper trading

Shadow trading is evidence collection, not approval. Broker-connected paper
trading can be proposed only when all conditions below are met:

| Gate | Minimum requirement |
| --- | --- |
| Forward sample | At least 60 closed shadow trades and at least 6 calendar months. |
| Trade quality | Positive average R and profit factor at least 1.20 after modeled costs. |
| Risk | Maximum drawdown no worse than 5% of model equity. |
| Reliability | No unresolved duplicate trade, stale-data, position-state, or Friday-close defect. |
| Review | Monthly review documents why performance is likely robust rather than one lucky sequence. |
| Approval | Sami explicitly approves a separate paper-trading specification. |

Passing a gate does not authorize live trading. Live trading requires a distinct
risk policy, broker adapter review, paper-trading results, and explicit approval.

## 9. Build order

1. **Complete:** Define local configuration and data/ledger schemas.
2. **Complete:** Extract the v3 signal engine into a reusable, read-only function.
3. **Complete:** Build the risk gateway and deterministic one-cycle simulator.
4. **Complete:** Build `ai_trade.shadow_runner`, which refreshes read-only IBKR
   SPY snapshots and runs only during the approved New York-time windows.
5. **Complete:** Add position monitoring, one-open-position protection,
   RRMS-tier recovery, and Friday-close simulation. Closed simulated trades are
   written to a separate immutable local ledger.
6. Next: build daily/monthly review reports and inspect the forward loop before
   considering paper execution.

### Starting the runner manually

With TWS/IB Gateway open and API socket clients enabled on port 7496, run:

```powershell
./scripts/start_shadow_runner.ps1
```

It stays running locally and checks once per minute. It requests read-only
market data only at the five permitted Monday–Thursday New York-time windows.
Do not configure an operating-system background task until the manual run has
been observed and reviewed for several sessions.

## 10. Non-goals

- No live orders, paper orders, credentials, account balances, or broker order
  endpoints.
- No automatic macro decision. The macro stance remains manually controlled
  until the Macro Dashboard publishes a tested regime value.
- No short-side implementation. Bearish logic requires a separately designed
  and tested strategy version.
- No strategy tuning based on individual forward trades. Rule changes require a
  new version and a fresh documented test.
