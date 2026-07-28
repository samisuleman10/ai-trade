# Strategy 04 v1.1 — robustness notes

## Year-by-year fixed-risk comparison

| Entry year | v1 P&L | v1.1 P&L | Change |
| --- | ---: | ---: | ---: |
| 2021 | $409.48 | $408.01 | -$1.47 |
| 2022 | -$934.08 | -$633.44 | +$300.65 |
| 2023 | $698.79 | $1,004.39 | +$305.60 |
| 2024 | -$340.03 | -$34.15 | +$305.88 |
| 2025 | $509.51 | $517.65 | +$8.14 |
| 2026 through July 16 | -$34.69 | -$17.55 | +$17.14 |

The improvement is not confined to one calendar year. The largest changes
occur in 2022–2024; 2021 is effectively unchanged and 2025–2026 improve only
slightly.

## Chronological-path interaction

The short trigger formula is unchanged, but the executed short-trade count
changes from 19 to 22. This is expected rather than a short-rule modification:

1. A deep long reaction is no longer a valid signal and does not consume its
   zone.
2. That zone can later produce a valid shallow long or role-flip into supply.
3. Removing weak longs also changes when the one-position-at-a-time engine is
   free to accept later short signals.

Candidate counts reflect the same causal path change:

- v1: 101 candidates — 48 long and 53 short.
- v1.1: 93 candidates — 35 long and 58 short.
- All 35 v1.1 long candidates have penetration no greater than 0.25; the
  observed maximum is 0.249999999999937.

## Interpretation

The temporal distribution is encouraging, but it is not a genuine
out-of-sample test. The 25% boundary was chosen after examining this entire
2021–2026 dataset. Version 1 remains the locked baseline until Version 1.1 is
tested on unseen dates or another comparable instrument without retuning.
