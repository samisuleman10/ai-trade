# Strategy 04: v1 versus v1.1

Version 1.1 changes only the long trigger: its low may penetrate no more than 25% of the demand-zone width.

| Sizing | Scope | v1 trades | v1 win rate | v1 P&L | v1.1 trades | v1.1 win rate | v1.1 P&L | P&L change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed | all | 42 | 54.8% | $308.97 | 38 | 63.2% | $1,244.92 | $+935.94 |
| fixed | long | 23 | 34.8% | $-1,176.44 | 16 | 50.0% | $-74.51 | $+1,101.93 |
| fixed | short | 19 | 78.9% | $1,485.42 | 22 | 72.7% | $1,319.43 | $-165.99 |
| rrms | all | 42 | 54.8% | $1,842.47 | 38 | 63.2% | $3,626.29 | $+1,783.82 |
| rrms | long | 23 | 34.8% | $-2,769.06 | 16 | 50.0% | $1,046.26 | $+3,815.32 |
| rrms | short | 19 | 78.9% | $4,611.53 | 22 | 72.7% | $2,580.03 | $-2,031.50 |

## Validation warning

The penetration threshold was discovered from this same historical sample. Improvement here is in-sample evidence, not proof of generalization. Preserve v1 as the baseline and validate v1.1 on unseen data before promotion.
