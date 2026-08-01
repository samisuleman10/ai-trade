---
title: HTF/LTF Alligator confluence — entry timing rule
status: falsified
owner: Sami
first_proposed: 2026-08-01
tested: 2026-08-01
result: did not replicate out-of-sample; see Outcome
---

# HTF/LTF Alligator confluence — entry timing rule

## Outcome — falsified, 2026-08-01

**Do not re-propose this as a fix to the Alligator entry.** Tested the same day
it was written, against already-recorded trades. Recorded in
`strategies/strategy_03/STATUS.md`.

**The entry this was meant to repair is itself dead.** The Alligator
mouth-opening entry at 15m fires the abandon rule on **seven of eight
instruments independently** — SPY, QQQ, DIA, IWM, GLD, SLV, EURUSD, with
GBPUSD inconclusive. Pooled: 5,602 trades, −0.1033R, **t = −8.23**. Strongest
result in the repository, and it does not depend on pooling. At 1h/4h the
result is inconclusive, which reflects sample size rather than a reprieve.

**The HTF-freshness mechanism did not replicate.** Tested as an explanation for
*why* the entry fails:

| Sample | r | p |
| --- | ---: | ---: |
| SPY + QQQ (where the idea was formed) | −0.113 | 0.054 |
| Seven instruments | −0.029 | 0.36 |

Three of the five newly added instruments pointed the wrong way. No HTF state
rescues the entry — the best available condition still loses at **t = −2.51**.
DIA was withheld from this test and never read, so it remains unspent as a
holdout.

## What is *not* falsified

Only the first clause was measured — HTF mouth freshness as a condition on the
existing mouth-opening entry. The second clause, **"otherwise wait for a proper
bullish or bearish flag"**, was never tested. It describes a structurally
different entry (impulse, consolidation, then break in the impulse direction),
not a trend-continuation entry on a mouth-open. It should not be treated as
falsified by the result above, and it should not be tested as another condition
bolted onto a dead entry.

Relevant constraint on any follow-up: two signal families are now falsified with
strong evidence, and both were trend-continuation entries with 1:1 targets. A
third idea should differ **structurally**, not incrementally.

---

## Original idea, as proposed

Kept verbatim as the record of what was tested.

### Problem observed

When adding higher-timeframe confluence to an Alligator entry, trades kept
retracing immediately after entry. Getting the higher timeframe to agree was
not enough on its own — agreement that has already been running for a while
means the move is late, and price pulls back against the fresh entry.

### Rule used discretionarily

Two cases, decided at signal time:

1. **Lower-timeframe Alligator is trending properly *and* the higher-timeframe
   Alligator has just opened** → enter directly, no further confirmation.

2. **Anything else** (HTF Alligator already open for some time, or LTF not
   cleanly trending) → do not enter on the signal. Wait for a proper bullish or
   bearish flag to form, and enter only on that.

The distinguishing variable is the *freshness* of the higher-timeframe
Alligator opening, not merely its direction. A just-opened HTF Alligator is
treated as permission to enter immediately; a mature one demands a
consolidation-then-continuation pattern first.

### Why it plausibly helped

An HTF Alligator that has been open for a while has already delivered part of
its move, so an entry there sits deep into an extended leg — exactly where
retracement is most likely. Requiring a flag in that case forces the entry to
wait out the retracement rather than absorb it.

### Open questions at the time

Clause 1's questions are now moot. Clause 2's remain open if the flag entry is
ever pursued on its own.

- ~~**"Just opened"** needs a numeric definition~~ — resolved by testing; no
  definition of freshness produces an edge.
- **"Trending properly"** on the lower timeframe — line order plus some minimum
  separation, and for how many bars.
- **Flag detection** needs a mechanical definition (impulse leg, then a
  counter-sloping or sideways consolidation within some retracement band, then
  break in the impulse direction).
- Worth noting: this was a discretionary observation, not a measured result.
  Testing the *mechanism* against already-recorded trades — one script, no new
  rules — settled it in a day. Do that first whenever an idea claims to explain
  why an existing signal fails.
