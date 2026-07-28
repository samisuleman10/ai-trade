---
strategy_id: strategy_02
version: v1
status: draft
asset_class: to_be_decided
instrument: to_be_decided
direction: to_be_decided
created: 2026-07-22
---

# Strategy 02 - Version 1

## 1. Hypothesis

Describe the market behaviour this strategy expects to exploit. This is a testable claim, not an indicator name.

> Pending: capture the Strategy 02 course notes, chart examples, and intended market.

## 2. Market and trading context

| Decision | Rule |
| --- | --- |
| Asset / instrument | Pending |
| Venue / data source | Pending |
| Trading direction | Pending: long, short, or both |
| Execution timeframe | Pending |
| Higher-timeframe context | Pending |
| Market-session rules | Pending |
| Overnight / weekend policy | Pending |
| Macro filter | Pending |

## 3. Indicator and data definitions

For every indicator or pattern, define the exact formula, inputs, timeframe,
and no-lookahead treatment. A chart label alone is not sufficient.

| Input / indicator | Exact definition | Purpose |
| --- | --- | --- |
| Pending | Pending | Pending |

## 4. Entry rules

Write each condition in a form Python can evaluate from completed bars.

### Long entry

Pending.

### Short entry

Pending.

### Trigger and order timing

Pending: specify whether entry occurs at the close of the qualifying bar, next-bar open, a limit order, or another defined rule.

## 5. Risk and exit rules

| Component | Exact rule |
| --- | --- |
| Initial stop | Pending |
| Target / reward-risk rule | Pending |
| Position sizing | Pending |
| Maximum concurrent positions | Pending |
| Early exit / invalidation | Pending |
| Friday / weekend handling | Pending |
| Daily loss / circuit-breaker rule | Pending |

## 6. Validation plan

1. Implement the rules without lookahead.
2. Backtest a long historical period with explicit costs and conservative fills.
3. Keep a final unseen period for out-of-sample evaluation.
4. Review every trade visually before interpreting performance metrics.
5. Run robustness checks: parameter sensitivity, slippage/cost stress, and Monte Carlo trade-sequence analysis.
6. Only if the evidence holds: run shadow mode, then consider paper trading.

## 7. Decisions and open questions

- What is the exact Strategy 02 setup from the course?
- Which instrument should be its first test market?
- Is it intended as an intraday, swing, or longer-term strategy?
- Which rules are discretionary today and must become numerical before testing?
