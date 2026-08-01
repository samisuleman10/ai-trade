# Strategy 04 — Version 1.3

> **Strategy 04 is closed (1 August 2026).** Its filters were falsified on instruments they were never fitted to, and the equity samples cannot resolve effects of the size claimed. Read [`../STATUS.md`](../STATUS.md) before acting on anything below. This document is kept as the historical record of what was specified, not as a live proposal.

## Purpose

Establish whether Strategy 04 has an edge worth tuning, before tuning it
further.

This version adds no rule and tests no filter. It exists because three filters
have now been evaluated against baselines that were never shown to differ from
zero, and a fourth would add another measurement of the same kind.

## Why this replaces the original v1.3

The first draft of this document asked whether the directional-body
requirement is symbol-dependent. That question assumed the underlying edge was
real and asked only how to shape it. The assumption does not hold.

Per-trade R on the recorded v1.1 fixed-risk ledgers:

| Symbol | Trades | Average R | SD | t |
| --- | ---: | ---: | ---: | ---: |
| SPY | 38 | +0.2184 | 0.9734 | 1.38 |
| DIA | 49 | +0.1770 | 0.9864 | 1.26 |
| QQQ | 59 | +0.0190 | 1.0079 | 0.15 |
| EURUSD | 243 | −0.0728 | 1.0038 | −1.13 |
| GBPUSD | 260 | −0.1192 | 1.0057 | −1.91 |

No symbol reaches the conventional bar of |t| ≈ 2. SPY, the strongest result,
would need roughly **79 trades** for its observed average to clear it and has
38. The t-test assumes independent trades, which holds approximately here since
only one position is open at a time; it is a guide, not a formal result, and it
makes no adjustment for the several filters already examined, which would make
the picture more pessimistic rather than less.

Three consequences:

1. **The filter comparisons compare noise to noise.** A filter that moves SPY
   by −$1,638 is moving a figure that is not itself distinguishable from zero.
2. **The symbol-dependence story is probably an artifact.** SPY and QQQ are
   highly correlated. A real market-structure effect should appear in both;
   opposite signs on instruments that move together is what sampling noise
   looks like.
3. **Every filter was discovered on SPY** — the 25% rule from the SPY long-loss
   review, v1.2's Filter A from SPY trade 21, Filter B from a SPY trade 1
   observation. Filters found on SPY improving SPY is the expected signature of
   fitting, and QQQ has been acting as an unacknowledged out-of-sample check
   that they keep failing.

## The decision rule, declared before running

Committed 30 July 2026, before any holdout run existed. A threshold chosen
after seeing results is not a threshold.

- **Accept** and continue development when: out-of-sample average R is
  **positive** with **|t| ≥ 2** on **any single symbol**.
- **Abandon** or fundamentally rethink when: out-of-sample average R is
  **negative** with **|t| ≥ 2** on **any single symbol**.
- **Judged on**: out-of-sample average R and its t, on the frozen configuration
  below, per symbol.

Notes that bind the interpretation:

- **|t| is compared against Student's t at that run's own degrees of freedom**,
  not a flat 2.0. At small n the 95% two-sided critical value is much larger —
  3.182 at four trades — and a flat 2.0 marked a four-trade run as conclusive
  during dashboard work. The stated "|t| ≥ 2" is shorthand for "clears the 95%
  two-sided critical value".
- **Both rules can fire at once**, on different symbols. That is not a
  contradiction to be resolved by picking the favourable one: it is the
  symbol-dependence claim finally being tested out-of-sample, and it must be
  reported as such.
- **Neither firing is also an outcome.** If the holdout settles nothing, the
  honest report is that the available data cannot validate this strategy — not
  that the question remains open pending another filter.

For reference, no sample has ever cleared the accept bar in this project. The
abandon bar is currently met in-sample by pooled FX (t = −2.16, 503 trades).

## Method

**1. Freeze.** Take v1.1 as shipped plus every filter examined to date — the
25% penetration limit, v1.2 Filter A, v1.2 Filter B, and the directional-body
requirement — at their current settings. No parameter is tuned during this
version.

**2. Holdout.** A strict chronological split was specified here and then
abandoned before running, because it is provably underpowered: every symbol's
holdout would need a larger effect than the one under test, so the answer would
have been "inconclusive" by construction. A **cross-instrument** holdout was
used instead — FX, which no filter was ever fitted to. The arithmetic and the
provenance evidence are recorded in `results/HOLDOUT_RESULT.md`.

A chronological test remains desirable and is not possible at current trade
counts. Revisit it when a holdout can detect an effect the size of the one
claimed.

**3. FX first.** EURUSD and GBPUSD carry 243 and 260 trades against 38–59 for
the equities. They are the only samples with enough weight to say anything, and
both currently point negative. If the strategy cannot work where the evidence
is strongest, per-symbol tuning on 38 SPY trades is beside the point.

**4. Report power, not just outcome.** Every result states its trade count and
t. A holdout that produces nine trades has not validated anything, which is the
limitation of the Strategy 02 precedent and must not be repeated silently.

## Explicit non-goals

- No new filter is proposed, implemented, or measured.
- No parameter is optimised.
- No symbol is made rule-conditional.

The directional-body question is deferred, not abandoned. It becomes worth
asking once a baseline exists that is distinguishable from zero. If no such
baseline emerges, the question was never answerable.

## Addressing the power problem

The 38-trade SPY sample cannot settle this. Three ways forward, to be chosen
explicitly rather than by default:

- **Extend history.** More years of cached bars raise the trade count directly.
- **Widen the instrument set.** More symbols under identical rules pool
  evidence, provided results are not cherry-picked afterwards.
- **Accept the limit.** State plainly that equity conclusions are provisional
  and that the strategy is not ready for a promotion decision.

## Promotion criteria

Version 1.3 does not promote anything. It produces one of two outcomes:

1. A frozen configuration with out-of-sample evidence meeting the pre-declared
   accept rule, at which point tuning questions such as the directional-body
   split become worth asking.
2. Evidence that no such configuration exists, at which point the honest step
   is to stop adding filters to Strategy 04.

Strategy 02 v1.5 reached outcome 2 and was recorded as failing its own gate.
That is the standard this version is held to.

No configuration is approved for paper or live execution by this document.
