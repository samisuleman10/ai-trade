# Strategy 02 v1.5

## Status

Locked historical-research version. Deterministic implementation and the full
validation package are complete. The strategy failed its fixed-risk
chronological out-of-sample gate and is not approved for shadow, paper, or live
trading.

## Validation result

The one-year holdout from 17 July 2025 through 16 July 2026 produced:

- 9 fixed-risk trades
- 44.44% win rate
- -$164.61 net P&L
- 0.69 profit factor
- -0.120 average R

RRMS ended $33.45 positive through variable sizing, but its underlying average
R was the same negative -0.120. It does not reverse the failed gate.

## Evidence

- `strategy.md` — locked trading rules
- `results/backtest/` — original full-sample backtest
- `results/validation/freeze_manifest.json` — source, data, configuration, and hashes
- `results/validation/out_of_sample_report.json` — chronological holdout
- `results/validation/parameter_sensitivity.csv` — 27 parameter runs
- `results/validation/cost_slippage_stress.csv` — 16 cost scenarios
- `results/validation/monte_carlo.json` — 10,000 seeded bootstrap paths
- `results/validation/trade_causality_audit.csv` — all 38 trades
- `results/validation/trade_review/` — chart pages covering trades 1–38
- `results/validation/VALIDATION_REPORT.md` — findings and promotion decision

The next valid step is additional forward evidence or a predeclared new strategy
version. The holdout must not be optimized into the current locked version.
