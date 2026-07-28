# Strategy 04 v1.1 — cross-asset filter decision

## Test design

Each comparison used identical cached 15-minute and one-hour data, trading
hours, stops, targets, transaction-cost assumptions, one-position rule, and
risk settings. Version 1.1 changed only the long demand-zone penetration rule:
the trigger low must remain within the upper 25% of demand.

## Fixed-risk results

| Symbol | v1 P&L | v1.1 P&L | Change | Decision |
| --- | ---: | ---: | ---: | --- |
| SPY | $308.97 | $1,244.92 | +$935.94 | v1.1 remains the research candidate |
| DIA | $349.50 | $1,295.23 | +$945.72 | v1.1 remains the research candidate |
| QQQ | $893.02 | $163.06 | -$729.96 | Do not use the 25% filter on QQQ |

## Interpretation

The 25% rule is **not universal**. It removes low-quality long reactions on
SPY and DIA, but removes profitable QQQ longs. This is valuable negative
evidence: applying a SPY-derived threshold to a correlated but different ETF
would have reduced fixed-risk QQQ performance.

## Current research status

- **SPY v1.1:** candidate for future shadow-mode validation with fixed 0.15%
  risk only.
- **DIA v1.1:** candidate for future shadow-mode validation with fixed 0.15%
  risk only.
- **QQQ:** retain Version 1 as the better historical fixed-risk baseline; do
  not activate v1.1 or any RRMS configuration.
- **RRMS:** four-loss reset is the safer locked policy, but sizing remains a
  separate experiment from signal validation.

No configuration is approved for live orders. The next validation stage is
forward, shadow-mode evidence with parameters frozen for each symbol.

## Evidence

- [SPY v1 versus v1.1](../../spy_1h_15m/COMPARISON.md)
- [QQQ v1 versus v1.1](../../qqq_1h_15m/COMPARISON.md)
- [DIA v1 versus v1.1](../../dia_1h_15m/COMPARISON.md)
