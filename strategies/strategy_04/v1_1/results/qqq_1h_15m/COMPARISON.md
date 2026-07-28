# Strategy 04: v1 versus v1.1

Version 1.1 changes only the long trigger: its low may penetrate no more than 25% of the demand-zone width.

| Sizing | Scope | v1 trades | v1 win rate | v1 P&L | v1.1 trades | v1.1 win rate | v1.1 P&L | P&L change |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed | all | 62 | 56.5% | $893.02 | 59 | 52.5% | $163.06 | $-729.96 |
| fixed | long | 30 | 60.0% | $760.45 | 24 | 54.2% | $190.51 | $-569.95 |
| fixed | short | 32 | 53.1% | $132.56 | 35 | 51.4% | $-27.45 | $-160.01 |
| rrms | all | 62 | 56.5% | $1,320.59 | 59 | 52.5% | $-993.83 | $-2,314.41 |
| rrms | long | 30 | 60.0% | $2,323.59 | 24 | 54.2% | $-239.02 | $-2,562.61 |
| rrms | short | 32 | 53.1% | $-1,003.00 | 35 | 51.4% | $-754.81 | $+248.19 |

## Validation warning

The penetration threshold was discovered from this same historical sample. Improvement here is in-sample evidence, not proof of generalization. Preserve v1 as the baseline and validate v1.1 on unseen data before promotion.
