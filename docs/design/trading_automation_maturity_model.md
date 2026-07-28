# Trading Automation Maturity Model

## Key distinction

An **order type** is a broker instruction: market, limit, stop-loss, or take-profit.  
**Algorithmic trading** is the programmable decision and risk logic that decides whether, when, and how to use those instructions.

For Strategy 01, the logic can be expressed as:

```text
IF the 1h, 15m, and 5m Alligators align
AND the session and macro-bias rules allow the direction
AND risk and exposure gates pass
THEN calculate size from the selected stop,
prepare an entry with a protective stop and target,
and monitor the position according to defined exit rules.
```

## Four levels

1. **Order automation** -- The trader identifies the setup. A position sizer calculates the size from account risk and stop distance, then prepares or submits a bracket order.
2. **Signal automation** -- The strategy detects a valid setup and creates an alert/proposed trade. The trader approves or rejects it.
3. **Rule-based execution** -- The strategy checks all rules and independently sends/manages the order. Hard safety controls and a manual kill switch remain mandatory.
4. **Systematic portfolio system** -- A portfolio-level system allocates capital among validated strategies, manages total risk/correlation, monitors degradation, and controls promotion/retirement of strategy versions.

## Position Sizer classification

The MetaTrader Position Sizer is **Level 1 order automation** if it converts the manually selected entry/stop/risk into a ready order with a derived take-profit. The trader still decides whether the trade exists. If it only displays numbers and does not create an order ticket, it is a risk calculator rather than automation.

## Current project status

We are currently at the early **Level 2** boundary:

- Read-only IBKR market data and local data cache
- Deterministic Strategy 01 variants and historical backtests
- Saved reports, charts, and strategy documentation
- Time-gated shadow signals; no broker-order permission

## Controlled promotion path

`shadow signals -> manual position-sizing/bracket preview -> IBKR paper orders -> one safety-gated automated strategy -> portfolio-level system`

No transition to paper or live execution happens merely because a backtest looks good. The strategy must pass out-of-sample testing, cost/slippage assumptions, Monte Carlo stress tests, and sustained shadow/paper monitoring first.
