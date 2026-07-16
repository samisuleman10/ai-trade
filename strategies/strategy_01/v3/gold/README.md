---
strategy_id: strategy_01
version: v3
market: gold
instrument_candidate: MGC Micro Gold futures
status: preliminary_historical_research
execution_mode: historical_data_only
parent_framework: ../spy/strategy.md
---

# Strategy 01 v3 — Gold / MGC

This is a separate Gold application of the locked Strategy 01 v3 framework.
It does not change the SPY strategy or inherit its historical results.

## Inherited framework

- 4-hour completed Alligator direction filter.
- 1-hour Heikin-Ashi + Alligator entries.
- Manual macro regime filter, initially bullish / long-only.
- No first-hour, last-hour, or Friday entries.
- One open position at a time and 1R initial target.

## Gold-specific rules

| Area | Rule |
| --- | --- |
| Historical instrument | IBKR `CONTFUT` MGC continuous futures; research only. |
| Execution instrument | A specific active MGC expiry, selected by a future rollover component. Never submit an order to `CONTFUT`. |
| Contract multiplier | 10 troy ounces. A USD 1.00/oz move equals USD 10 per MGC contract. |
| Minimum tick | USD 0.10/oz = USD 1 per MGC contract. |
| Session basis | CME Globex daily session, 18:00–17:00 New York time. |
| Entry window | 19:00–16:00 New York time: excludes the first and final Globex hour. Sunday entry signals are excluded for this first test. |
| Friday | No new Friday entries; force-close in the final Friday 1-hour bar containing 17:00 New York time. |
| Sizing | Whole contracts only. `risk per contract = abs(entry − stop) × 10`. A setup is rejected if the 0.15% account-risk budget cannot buy one contract. |
| Costs | USD 0.72 per contract per side fee-recovery floor (USD 0.70 COMEX + USD 0.02 regulatory). Broker commission and roll costs remain unmodelled. |

## Required interpretation

The Gold test is preliminary even after it runs. The fee floor is not a complete
commission model, and a continuous futures series does not include the costs or
implementation details of rolling real contracts. Any future paper/live phase
must add a verified IBKR commission schedule, margin/buying-power control,
front-month selection, delivery avoidance, and roll rules.

No paper or live trading is authorised.
