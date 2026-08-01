---
title: HTF/LTF Alligator confluence — entry timing rule
status: tested, not supported
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


## Tested 1 August 2026 — the mechanism does not replicate

Run before any strategy was written, against Strategy 03 v1's recorded 15m
trades: `python scripts/analyze_htf_alligator_age.py`. The pre-stated test was
the correlation between HTF mouth age and trade R, with the hypothesis
predicting r < 0.

On SPY and QQQ alone the gradient looked real — r = −0.113, p = 0.054, and the
five age buckets fell monotonically from +0.024R to −0.285R. Five further
instruments were then backtested and the same frozen analysis re-run.

**It did not hold up.** Across seven instruments and 982 agreeing trades,
r = −0.029, p = 0.36. Per instrument:

| | SPY | QQQ | IWM | GLD | SLV | EURUSD | GBPUSD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r | −0.118 | −0.108 | **+0.030** | **+0.052** | −0.064 | −0.011 | **+0.005** |

Three of the five new instruments point the wrong way. The bucket gradient also
broke: the oldest bucket (13+) came back at −0.000R, and the youngest at
−0.026R rather than positive. On 4h, r = −0.035, p = 0.33.

The SPY/QQQ gradient was noise. Two instruments agreeing in direction is not
evidence when five more disagree.

## What the same run did establish

No higher-timeframe Alligator state rescues the entry. On 1h, every group loses
significantly: agreeing −0.0715R (t = −2.51), opposing −0.1097R (t = −3.07),
mouth closed −0.1154R (t = −6.84). The best available HTF condition is still a
losing configuration on 982 trades.

DIA was withheld throughout and never read, so it remains unspent.

**This idea is closed.** Not because it was a bad observation — the discretionary
reading was reasonable and the SPY/QQQ result initially supported it — but
because the prediction it makes is testable and the test came back negative on
data it had never seen.

**One clause was never tested.** The rule had a second half — *otherwise wait
for a proper bullish or bearish flag* — and only the first half was measured.
The analysis conditioned the existing mouth-opening entry on HTF mouth age; it
never operationalised the flag. That clause describes a structurally different
entry (impulse, then consolidation, then break in the impulse direction) rather
than a trend-continuation entry on a mouth-open, so it is untested rather than
falsified. If it is ever pursued it needs its own signal and its own recorded
trades — not another condition bolted onto this entry, which the result above
closes.

Where the search went next: `next_strategy_direction.md`.
