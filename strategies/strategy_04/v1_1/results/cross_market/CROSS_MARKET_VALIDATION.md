# Strategy 04 v1.1 — cross-market cached-data test

The 25% long-zone penetration threshold is unchanged across every symbol.

## Fixed 0.15% risk

| Symbol | Period | Trades | Win rate | Net P&L | PF | Avg R | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 2021-04-14 to 2026-07-16 | 38 | 63.2% | $1,244.92 | 1.57 | 0.218 | $633.44 |
| QQQ | 2021-03-09 to 2026-07-23 | 59 | 52.5% | $163.06 | 1.04 | 0.019 | $1,387.66 |
| DIA | 2021-03-09 to 2026-07-23 | 49 | 61.2% | $1,295.23 | 1.43 | 0.177 | $528.89 |

## Five-loss RRMS

| Symbol | Trades | Win rate | Net P&L | PF | Avg R | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 38 | 63.2% | $3,626.29 | 2.07 | 0.218 | $1,231.03 |
| QQQ | 59 | 52.5% | $-993.83 | 0.92 | 0.019 | $7,234.14 |
| DIA | 49 | 61.2% | $4,468.49 | 1.84 | 0.177 | $1,292.79 |

## Interpretation boundary

QQQ and DIA are out-of-symbol checks, not independent macro regimes: they are correlated US equity-index ETFs. Positive results on both would strengthen confidence that the rule is not SPY-only, but they do not prove generalization. Futures require their own contract multiplier, cost, and session model.
