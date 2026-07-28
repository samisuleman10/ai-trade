# Strategy 02 v1.5 Validation Report

**Validation date:** 23 July 2026  
**Status:** Historical research only  
**Promotion decision:** Do not promote to shadow or paper trading

## Frozen baseline

Strategy 02 v1.5 was frozen before validation. The exact strategy parameters,
backtest configuration, source files, data files, byte sizes, and SHA-256 hashes
are recorded in `freeze_manifest.json`.

The baseline uses:

- SPY
- 1-hour completed Heikin-Ashi reversal confirmation
- 15-minute Alligator direction alignment
- 15-minute confirmed ZigZag structure
- Next 15-minute bar open entry
- Structure plus ATR-buffer stop
- 1:1 target
- 0.15% fixed risk or RRMS sizing
- 1 bp adverse slippage per side
- USD 0.005 commission per share per side

## Strict chronological out-of-sample test

The final year was held out:

| Segment | Range | Trades | Win rate | Net P&L | Profit factor | Average R |
|---|---|---:|---:|---:|---:|---:|
| Training, fixed risk | Apr 2021–16 Jul 2025 | 29 | 62.07% | +$1,304.05 | 2.15 | +0.301 |
| Out of sample, fixed risk | 17 Jul 2025–16 Jul 2026 | 9 | 44.44% | -$164.61 | 0.69 | -0.120 |
| Training, RRMS | Apr 2021–16 Jul 2025 | 29 | 62.07% | +$2,016.80 | 2.67 | +0.301 |
| Out of sample, RRMS | 17 Jul 2025–16 Jul 2026 | 9 | 44.44% | +$33.45 | 1.04 | -0.120 |

The fixed-risk edge did not persist in the holdout. RRMS produced a marginal
positive dollar result only because it changed sizing after losses; the
underlying average R remained negative. This is a failed promotion gate.

## Parameter sensitivity

Twenty-seven causal reruns varied:

- ZigZag depth: 14, 18, 22
- ZigZag deviation: 3, 5, 7 ticks
- ZigZag backstep: 2, 3, 4

All 27 combinations generated the same realised baseline result. Within these
ranges, the confirmed extremes used by executable trades did not change. This
shows local stability but does not provide 27 independent confirmations; it
also indicates that the tested deviation range is too small relative to SPY's
price movement to be discriminating.

## Cost and slippage stress

Sixteen runs combined:

- Slippage: 0, 1, 2, and 5 bps per side
- Commission: $0, $0.005, $0.01, and $0.02 per share per side

All 16 full-sample runs remained profitable. The worst tested case—5 bps
slippage and $0.02 commission per share per side—produced:

- 38 trades
- 55.26% win rate
- +$738.91 net P&L
- 1.42 profit factor
- +0.133 average R
- $671.21 maximum drawdown

This is encouraging cost robustness on the full sample, but it does not repair
the negative fixed-risk out-of-sample result.

## Monte Carlo bootstrap

Ten thousand seeded bootstrap paths resampled the 38 observed fixed-risk R
outcomes:

| Measure | Result |
|---|---:|
| Ending equity, 5th percentile | $99,897.58 |
| Ending equity, median | $101,159.18 |
| Ending equity, 95th percentile | $102,416.63 |
| Probability of ending below start | 6.54% |
| Maximum drawdown, median | $462.35 |
| Maximum drawdown, 95th percentile | $959.14 |
| Maximum drawdown, 99th percentile | $1,271.21 |
| Maximum losing streak, median | 4 |
| Maximum losing streak, 95th percentile | 6 |

This bootstrap is conditional on a small historical sample. It does not model
regime changes or serial dependence and therefore must not override the
chronological holdout result.

## Complete trade audit

All 38 fixed-risk trades were reconstructed from the locked signal engine and
checked for:

- A matching causal signal
- Decision timestamp equal to the next executable bar open
- Structure confirmation no later than the decision
- Pivot timestamp no later than its confirmation
- Entry price equal to next-bar open plus adverse slippage
- Exit not preceding entry
- Correct long/short stop geometry
- Correct long/short target geometry

All 38 trades passed all eight automated causality and timing checks. Detailed
rows are in `trade_causality_audit.csv`.

Ten deterministic chart pages cover trades 1–38 under `trade_review/`. Each
page shows candlesticks around entry and exit, entry/stop/target/exit levels,
entry and exit timestamps, exit reason, and net P&L. PNG renderings accompany
the SVG sources.

## Findings

1. No automated timing, entry-price, structure-confirmation, or stop/target
   geometry violation was found in the 38 realised trades.
2. The full-sample result is robust to the tested transaction-cost range.
3. The selected ZigZag grid is locally insensitive and therefore not evidence
   of a uniquely optimal parameter choice.
4. Only nine out-of-sample trades exist, which is too small for a confident
   estimate.
5. Fixed-risk performance was negative out of sample.
6. RRMS masked the negative out-of-sample average R through variable sizing.
7. Fourteen of 38 full-sample exits were Friday closes, making results dependent
   on the weekend-close rule.

## Decision

Strategy 02 v1.5 does not pass the out-of-sample promotion gate. It must not be
connected to IBKR Paper or Co-Invest.

The appropriate next research action is not parameter optimization on the
holdout. Preserve this holdout result, collect additional forward data, and
investigate whether the reversal premise needs a predeclared regime or macro
filter in a new strategy version.
