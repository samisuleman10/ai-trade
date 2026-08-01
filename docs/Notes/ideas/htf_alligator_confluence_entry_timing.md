---
title: HTF/LTF Alligator confluence — entry timing rule
status: proposed
owner: Sami
first_proposed: 2026-08-01
---

# HTF/LTF Alligator confluence — entry timing rule

## Problem observed

When adding higher-timeframe confluence to an Alligator entry, trades kept
retracing immediately after entry. Getting the higher timeframe to agree was
not enough on its own — agreement that has already been running for a while
means the move is late, and price pulls back against the fresh entry.

## Rule used discretionarily

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

## Why it plausibly helps

An HTF Alligator that has been open for a while has already delivered part of
its move, so an entry there sits deep into an extended leg — exactly where
retracement is most likely. Requiring a flag in that case forces the entry to
wait out the retracement rather than absorb it.

## Open questions before this can be coded

- **"Just opened"** needs a numeric definition — e.g. the HTF Alligator lines
  separated within the last *N* HTF bars, or jaw/teeth/lips spread crossing a
  threshold within *N* bars.
- **"Trending properly"** on the lower timeframe needs the same treatment —
  line order plus some minimum separation, and for how many bars.
- **Flag detection** needs a mechanical definition (impulse leg, then a
  counter-sloping or sideways consolidation within some retracement band, then
  break in the impulse direction).
- Which timeframe pair this was observed on, and whether the rule survives on
  the pairs already cached.
- Worth noting: this is a discretionary observation, not a measured result. It
  is a hypothesis to test out-of-sample, and it adds two more fitted parameters
  to a system that per `docs/research_direction.md` already has more filters
  than statistical power to judge them.
