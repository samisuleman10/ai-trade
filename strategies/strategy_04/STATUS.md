# Strategy 04 Current Status

**Closed 1 August 2026. Historical research only; not approved for shadow,
paper, or live trading. No further filter should be added to this strategy.**

Strategy 04 v1.3 reached outcome 2 of its own promotion criteria — "evidence
that no such configuration exists, at which point the honest step is to stop
adding filters to Strategy 04." This file records that outcome, in the same
form as `strategies/strategy_02/STATUS.md`.

## What was done

v1 (one-hour zones, fifteen-minute rejection entry) → v1.1 (a long trigger may
cut no more than 25% into the demand zone) → v1.2 (Filters A and B, run as a
base/A/B/AB ablation across eight instruments) → v1.3 (no new rule; a decision
rule declared in advance, and a cross-instrument holdout evaluated against it).

All 32 v1.2 runs have been scored under v1.3's committed accept/abandon rule.

## Result

**The accept rule fired zero times. The abandon rule fired five times**, every
one of them a filtered configuration on an instrument the filters had never
seen.

| Group | Runs | Accept | Abandon |
| --- | ---: | ---: | ---: |
| SPY, QQQ, DIA — in-sample | 12 | 0 | 0 |
| IWM, GLD, SLV — holdout | 12 | 0 | 0 |
| EURUSD, GBPUSD — holdout | 8 | 0 | 5 |

### 1. The filters encode the SPY sample, not a property of the market

On FX — 119 to 260 trades, the only samples with the power to conclude
anything — the unfiltered configurations are inconclusive (EURUSD base
t = −1.13, GBPUSD base t = −1.91) and *every* configuration that adds a filter
becomes conclusively losing, worst at GBPUSD A+B, t = −3.11. Filters built to
improve the strategy measurably degrade it on instruments they were not fitted
to.

IWM, GLD and SLV, cached two days after the filters were specified, said the
same thing more weakly: twelve runs, none significant, and Filter B's direction
inconsistent across them (GLD +0.204R, SLV −0.161R, IWM −0.118R).

### 2. The equity evidence cannot settle anything, and never could

All twelve in-sample equity runs miss the bar; the closest, DIA A+B, reaches
t = +1.99 against a critical value of 2.056. Their smallest detectable effects
run from ±0.36R to ±0.77R against observed effects of +0.02R to +0.36R — every
equity number in this strategy is smaller than the smallest effect its own
sample could resolve. This is a property of 38–59 trades over five years, not
of any particular filter.

### 3. The underlying idea is not merely unproven

Pooled FX — 503 trades, the most statistically powerful sample in the project —
is −0.0968R at t = −2.16. The committed rule excludes pooled results because
they are not a single symbol, so this fires nothing and is reported as context.
As evidence it points down, and it is the only place the base idea has been
measured with enough trades to point anywhere.

## The trap that will reopen this if it is not written down

GLD's Filter B row is the largest effect anywhere in the ablation: −$1,333.52
to +$578.52, a **+$1,912.04** swing, win rate 0.417 → 0.632. Read as P&L it is
the most encouraging number the project has produced.

It is not a result. Nineteen trades give t = +0.89 against a bar of 2.101, and
could only have resolved an effect of ±0.639R — more than three times the
+0.204R observed. Confirming an edge that size on GLD would need roughly 186
trades; GLD yields about 3.7 filtered trades a year, so on the order of fifty
further years of data. **It is not confirmable on this instrument and is not an
open lead.**

## Holdout instruments are spent

| Instruments | Became a holdout | Examined, and therefore burned |
| --- | --- | --- |
| EURUSD, GBPUSD | 2026-07-29 23:17 (`6c503e4`) | 2026-07-30 |
| IWM, GLD, SLV | 2026-07-31 16:40 (`55f381e`) | 2026-08-01 |

Both became holdouts by accident, because their data happened to arrive after
Filters A and B were specified at 2026-07-29 10:58 (`bffe4f2`). Neither is
pristine now. Anything designed after 1 August 2026 needs instruments that
appear nowhere in this table, declared before the design work starts —
`VersionSpec.holdout_symbols` exists for that and should be used prospectively
rather than discovered afterwards.

## Evidence

- `v1_3/results/HOLDOUT_RESULT.md` — both holdout evaluations, FX and metals
- `v1_2/results/ABLATION.md` — the 32-run ablation, with per-symbol provenance
- `v1_2/results/sweep/SWEEP.md` — max_risk_zone_ratio sensitivity, all 8 symbols
- `scripts/evaluate_holdout_significance.py` — the decision rule as runnable
  code; it reproduces every published FX verdict exactly and imports nothing
  from `ai_trade`

## What would justify reopening this

Not another filter. A filter added now would measure a smaller effect on
samples already shown incapable of resolving larger ones, and would spend
instruments that no longer exist. Reopening needs a change in the *evidence
base*, not the rules: materially more trades per instrument, on instruments not
listed above.
