---
title: Next strategy — what has been ruled out, and where the evidence points
status: exploring
owner: Sami
first_proposed: 2026-08-01
---

# Next strategy — what has been ruled out, and where the evidence points

**This is deliberately unnumbered.** `strategy_05` is reserved for whatever
actually earns a spec and lands on the dashboard. Idea-stage work lives here
under its own name; taking the number first makes an exploration look like a
commitment, and two of the last three numbered strategies were closed as
falsified.

## What was ruled out, 1 August 2026

Two signal families are now closed with strong evidence.

| Family | Instruments | Trades | Avg R | t | Record |
| --- | ---: | ---: | ---: | ---: | --- |
| Zone reaction + filters (S04) | 8 | 649 equity + FX | see below | — | `strategies/strategy_04/STATUS.md` |
| Alligator mouth opening, 15m (S03) | 8 | 5,602 | −0.1033 | **−8.23** | `strategies/strategy_03/STATUS.md` |

- **Strategy 04** — filters falsified on every instrument they were never
  fitted to; equity samples too small to resolve the effects claimed; the base
  idea is −0.0968R at t = −2.16 on pooled FX.
- **Strategy 03** — the Alligator entry fires the abandon rule on seven of
  eight instruments *independently*. No higher-timeframe state rescues it.
- **The HTF-freshness fix** (`htf_alligator_confluence_entry_timing.md`) looked
  real on SPY+QQQ (r = −0.113, p = 0.054) and vanished across seven
  instruments (r = −0.029, p = 0.36). Closed.

## The structural pattern worth noticing

Both falsified families are **trend-continuation entries with 1:1 targets**:
enter in the direction of the move, take profit at one unit of risk. Across
eight instruments and two unrelated signal definitions, they lose by a similar
amount. That consistency is information. It argues against a third
continuation variant, and it is why the mean-reversion direction below is
evidence-driven rather than a guess.

## Candidate direction: mean reversion

Fade the stretch instead of following it. Price extends unusually far from a
reference level (moving average, session open, VWAP, prior close), and the
trade bets on a move back toward that reference rather than a continuation
away from it.

The trade profile inverts: high win rate, small winners, occasional large
losers — failing in trends where continuation succeeds, and succeeding in the
chop where continuation bleeds. The existing 1:1 bracket discipline caps the
left tail that usually makes this family dangerous.

## Two traps in "the opposite of a loser is a winner"

Reversing a −0.10R system does **not** give +0.10R.

1. **Costs subtract in both directions.** Gross edge = net + costs. At roughly
   0.03R of costs, the true continuation edge is about −0.07R, so a reversed
   version is around **+0.04R net**, not +0.10R.
2. **The backtester assumes "stop before target"** when one bar's range
   contains both. That is deliberately pessimistic, and on 15m bars with a
   tight 1:1 bracket it may fire often. An unknown share of the −0.1033R could
   be that assumption rather than a market effect — and reversing the direction
   inherits the same penalty rather than escaping it.

## Measurements to run before any strategy is written

Testing the mechanism on already-recorded trades is what closed the HTF idea
for the price of one script, and it is the right first move again.

1. ~~**How much of the −0.1033R is the collision assumption?**~~ **Run
   2026-08-01: mostly not.** Collisions are 1.1–2.5% of trades and zero on FX.
   Pricing every one as a target fill moves the pooled result from −0.1033R
   (t = −8.23) to −0.0743R (t = −5.90) — decisive either way. But the
   per-instrument claim is assumption-sensitive: only four of eight still fire
   under the optimistic bound, and QQQ falls from t = −2.54 to −0.58. Strategy
   04 is unaffected (2 collisions in 760 trades). See
   `scripts/analyze_bracket_collisions.py`.

   **The reversal arithmetic changes accordingly.** Fading a −0.0743R signal,
   not a −0.1033R one, and after costs subtract in both directions the
   reversed edge is smaller again — plausibly near zero.
2. **Does mean reversion exist in this data at all?** Per instrument, bucket
   forward returns by how far price closed from a moving average in ATR units.
   No gradient means no amount of rule-craft will find one.

## Constraints any candidate must satisfy

Carried over from what killed Strategy 04:

- **Pre-registered power budget.** If the design cannot yield roughly 150
  trades per instrument on cached data, it cannot be falsified and should not
  be built. The Alligator's ~150 trades/year/instrument clears this easily;
  Strategy 04's 8–11 never could.
- **Holdout declared before design, not discovered after.** FX was burned
  2026-07-30 and IWM/GLD/SLV on 2026-08-01 for Strategy 04's filters.
  **DIA is unspent** — it was withheld from the HTF analysis and never read.
- **Separate authors for rules and audit.** See the strategy-research skill.
