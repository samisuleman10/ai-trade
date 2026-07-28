# Strategy 04: v1 versus v1.1

Version 1.1 changes only the long trigger: its low may penetrate no more than 25% of the demand-zone width.

| Sizing | Scope | v1 trades | v1 win rate | v1 P&L | v1.1 trades | v1.1 win rate | v1.1 P&L | P&L change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed | all | 53 | 54.7% | $349.50 | 49 | 61.2% | $1,295.23 | $+945.72 |
| fixed | long | 27 | 44.4% | $-662.50 | 22 | 54.5% | $138.06 | $+800.56 |
| fixed | short | 26 | 65.4% | $1,012.00 | 27 | 66.7% | $1,157.16 | $+145.16 |
| rrms | all | 53 | 54.7% | $-360.06 | 49 | 61.2% | $4,468.49 | $+4,828.55 |
| rrms | long | 27 | 44.4% | $-1,343.30 | 22 | 54.5% | $611.62 | $+1,954.93 |
| rrms | short | 26 | 65.4% | $983.24 | 27 | 66.7% | $3,856.87 | $+2,873.62 |

## Validation warning

The penetration threshold was discovered from this same historical sample. Improvement here is in-sample evidence, not proof of generalization. Preserve v1 as the baseline and validate v1.1 on unseen data before promotion.
