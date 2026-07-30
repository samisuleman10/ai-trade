# Strategy 04 v1 — long-loss review

## Scope

- Long trades: 23.
- Losing longs: 15.
- Winning longs: 8.
- Saved losing-long charts: 15.
- Strategy rules changed during review: **No**.

## Loss versus win diagnostics

| Feature | Losing longs | Winning longs |
| --- | ---: | ---: |
| Mean zone age | 165.6 hours | 130.7 hours |
| Mean zone width | 0.369 ATR | 0.307 ATR |
| Mean trigger body | 0.296 ATR | 0.242 ATR |
| Mean trigger range | 0.707 ATR | 0.538 ATR |
| Mean zone penetration | 0.48× zone width | 0.28× zone width |
| Mean entry extension | 0.435 ATR | 0.396 ATR |
| Mean planned risk | 0.854 ATR | 0.753 ATR |
| Mean holding time | 2.37 hours | 4.53 hours |

## Structural flags

| Flag | Losing longs | Winning longs |
| --- | ---: | ---: |
| Trigger traded below zone lower boundary | 1 (6.7%) | 1 (12.5%) |
| Trigger had already crossed the future stop | 1 (6.7%) | 1 (12.5%) |
| Entry extended more than 0.25 ATR above zone | 11 (73.3%) | 5 (62.5%) |
| Zone older than 120 hours | 6 (40.0%) | 5 (62.5%) |
| Stop occurred in the entry bar | 2 (13.3%) | 0 (0.0%) |

## Distributions

- Losing-long qualification scores: {'2': 7, '3': 7, '4': 1}.
- Winning-long qualification scores: {'2': 2, '3': 4, '4': 2}.
- Losing-long zone states: {'active': 7, 'rejected': 1, 'touched': 1, 'verified': 6}.
- Winning-long zone states: {'active': 3, 'verified': 5}.
- Losing-long entry hours: {'10': 2, '11': 6, '12': 2, '13': 1, '14': 4}.
- Winning-long entry hours: {'10': 2, '11': 3, '12': 1, '13': 1, '14': 1}.
- Losing-long years: {'2021': 1, '2022': 4, '2023': 1, '2024': 4, '2025': 2, '2026': 3}.
- Winning-long years: {'2021': 3, '2024': 1, '2025': 2, '2026': 2}.

## Evidence

- [All losing-long charts](charts/index.html)
- [Losing-long diagnostics](long_loss_diagnostics.csv)
- [All-long comparison data](all_long_diagnostics.csv)
- [Machine-readable comparison](long_comparison.json)

This review is descriptive. A filter should not be added until the chart audit
confirms that a repeated feature is economically meaningful rather than fitted
to these fifteen losses.
