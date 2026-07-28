# Strategy 04 v1 — losing-long findings

## Decision

The original Strategy 04 v1 rules remain unchanged. This review identifies
hypotheses for a separate comparison run; it does not retrofit filters to the
reported baseline.

## Baseline

- Long trades: 23
- Wins: 8
- Losses: 15
- Win rate: 34.8%
- Fixed-risk net P&L: -$1,176.44
- Mean result: -0.343R

## Strongest observed pattern: deep demand-zone penetration

| 15-minute trigger penetration | Trades | Wins | Losses | Win rate |
| --- | ---: | ---: | ---: | ---: |
| No more than 25% of zone width | 14 | 7 | 7 | 50.0% |
| More than 25% of zone width | 9 | 1 | 8 | 11.1% |
| More than 50% of zone width | 6 | 1 | 5 | 16.7% |

Keeping only the shallow-penetration group would have changed the long-side
fixed-risk result to -$68.71 and -0.034R per trade. It removed nine trades:
eight losses and one win. This is the best first hypothesis to retest.

Economic interpretation: a bullish reaction that must travel deeply through
the demand zone before closing back above it may represent weak support or a
liquidity sweep with insufficient rejection. A shallow touch followed by a
bullish close is a cleaner reaction.

## Secondary patterns

| Diagnostic group | Trades | Wins | Losses | Win rate |
| --- | ---: | ---: | ---: | ---: |
| Trigger range <= 0.60 ATR | 15 | 6 | 9 | 40.0% |
| Trigger range > 0.60 ATR | 8 | 2 | 6 | 25.0% |
| Entry extension <= 0.25 ATR | 7 | 3 | 4 | 42.9% |
| Entry extension > 0.25 ATR | 16 | 5 | 11 | 31.2% |
| Qualification score >= 3 | 14 | 6 | 8 | 42.9% |
| Qualification score >= 4 | 3 | 2 | 1 | 66.7% |

These directions are plausible, but their separation is weaker or their
sample is too small. In particular, Q4 has only three long trades and should
not be promoted to a rule from this result.

## What did not explain the losses

- Old zones were not worse: 40.0% of losses versus 62.5% of wins came from
  zones older than 120 hours.
- A trigger trading below the zone or through the later stop occurred in only
  one loss and one win.
- Entry time did not reveal a clean cluster.
- Zone state did not provide a clean separation: both active and verified
  demand zones produced losses and wins.

## Regime warning

Long performance varied considerably by year. All four 2022 longs and the
single 2023 long lost, while 2021 produced three wins from four longs. The
2024 sample was also weak (one win, four losses), so a simple bear-market
explanation is insufficient. A later macro/trend regime filter should be
tested independently rather than assumed.

## Recommended next experiment

Create a separate comparison run that changes only one condition:

> Allow a long trigger only when its low penetrates no more than 25% of the
> active demand-zone width.

Keep short rules, costs, timing, stops, targets, and position sizing identical.
Then compare the baseline and filtered variants on the same saved data and on
an out-of-sample period. Do not combine the range, extension, or Q-score
filters in the first test.

## Evidence

- [All 15 losing-long charts](charts/index.html)
- [Generated diagnostic report](LONG_LOSS_REVIEW.md)
- [All-long diagnostic data](all_long_diagnostics.csv)
- [First losing-long PNG preview](preview_long_loss_001.png)

