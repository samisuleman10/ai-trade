# Strategy 01 — status

**All five versions are closed.** Recorded 1 August 2026, v3 resolved the same
day once the missing data was generated.

`strategies/strategy_03/STATUS.md` established that the 15-minute Alligator
mouth-opening entry loses across eight instruments (5,602 trades, −0.1033R,
t = −8.23) and noted that Strategy 01 is built on the same indicator, so "any
Strategy 01 work should begin by asking whether its entry inherits this."

This is that measurement.

## What each version actually enters on

| Version | Confirmation | Entry | Extra filter |
| --- | --- | --- | --- |
| v1 | 1h Alligator open | **15m** Alligator open | 15m Heikin Ashi body beyond Lips |
| v2 | 1h Alligator open | **15m** Alligator open | 15m Heikin Ashi body beyond Lips |
| v3 | **4h** Alligator open | **1h** Alligator open | 1h Heikin Ashi body beyond Lips |
| v4 | 1h + 15m alignment | **15m** Alligator open | 15m Heikin Ashi body beyond Lips |
| v5 | as v4 | **15m** Alligator open | as v4, plus dynamic ATR jaw buffer |

Four of the five versions are 15-minute Alligator mouth-opening entries — the
exact signal Strategy 03 falsified. They differ from Strategy 03 only by
requiring the 1-hour Alligator to agree and the Heikin Ashi body to sit beyond
the Lips. v3 is not: it moves the whole structure up a band, into the region
Strategy 03 had recorded as inconclusive. Band 2 below resolves that region.

## The test

`scripts/analyze_strategy_01_inheritance.py` re-labels Strategy 03's recorded
trades with Strategy 01's two extra conditions, using Strategy 01's own
definitions imported from `ai_trade.strategy_01` rather than reimplemented. It
asks one question: **do those filters rescue an entry that loses without
them?**

The signal bar is the completed bar before entry. Because that convention
matters, both it and the alternative are reported. Trades with no confirmation
data are excluded from *both* columns so the comparison stays like-for-like.

**Validity check.** With no coverage restriction the 15m band reproduces the
published Strategy 03 figures exactly: 5,602 trades, −0.1033R, t = −8.23.

## Band 1: v1, v2, v4, v5 — the filters do not rescue the entry

Signal = bar before `decision_timestamp`; 1h confirmation over a 15m entry:

| Instrument | Covered n | R | t | Gated n | Gated R | Gated t |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 795 | −0.0981 | −2.85 | 122 | −0.0848 | −0.99 |
| QQQ | 805 | −0.0867 | −2.54 | 120 | −0.0268 | −0.30 |
| DIA | 806 | −0.0910 | −2.63 | 136 | −0.0683 | −0.86 |
| IWM | 834 | −0.1236 | −3.70 | 126 | −0.1364 | −1.62 |
| GLD | 725 | −0.1127 | −3.19 | 114 | **+0.0502** | +0.58 |
| SLV | 734 | −0.1654 | −4.59 | 120 | −0.1090 | −1.35 |
| EURUSD | 414 | −0.0896 | −2.49 | 98 | −0.1417 | −2.07 |
| GBPUSD | 487 | −0.0336 | −0.93 | 128 | −0.0240 | −0.37 |
| **Pooled** | **5,600** | **−0.1037** | **−8.26** | **964** | **−0.0668** | **−2.35** |

The gate keeps 17.2% of trades. Under the alternative convention it keeps
15.8% and the gated pool is −0.0536R at t = −1.81.

**The filters help, and not enough.** They lift the pooled result from
−0.1037R to −0.0668R — a real improvement, and still a losing configuration.
Every instrument except GLD stays negative, GLD's positive figure is noise at
t = +0.58, and no gated per-instrument result is favourable and significant.
There is no subset here that makes money.

## Band 2: v3 — resolved, and it fails too

The first run of this band was empty: only SPY, QQQ and DIA had a 1h ledger,
and SPY lost 153 of 253 trades because its 4h cache was short. Both gaps have
since been filled:

- **1h ledgers generated** for IWM, GLD, SLV, EURUSD and GBPUSD with the
  committed runner, taking the band from 865 trades to 2,681.
- **4h bars derived** from the 1h cache by `scripts/resample_1h_to_4h.py`,
  which recovers SPY's missing three years and gives spot FX 4h bars for the
  first time.

Signal = bar before `decision_timestamp`; 4h confirmation over a 1h entry:

| Instrument | Covered n | R | t | Gated n | Gated R | Gated t |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 253 | −0.0011 | −0.02 | 44 | −0.0195 | −0.17 |
| QQQ | 294 | −0.0137 | −0.27 | 51 | −0.0666 | −0.61 |
| DIA | 317 | −0.0356 | −0.71 | 53 | +0.0210 | +0.20 |
| IWM | 309 | −0.0982 | −1.98 | 42 | **−0.3214** | **−2.83** |
| GLD | 324 | −0.0281 | −0.58 | 49 | +0.0895 | +0.85 |
| SLV | 313 | −0.0964 | −1.94 | 45 | −0.1761 | −1.58 |
| EURUSD | 402 | −0.0606 | −1.78 | 84 | −0.0702 | −1.12 |
| GBPUSD | 465 | −0.0010 | −0.03 | 102 | −0.0499 | −0.73 |
| **Pooled** | **2,677** | **−0.0411** | **−2.56** | **470** | **−0.0663** | **−2.01** |

Under the alternative convention the gated pool is 431 trades at −0.0499R,
t = −1.47. Four trades are dropped for confirmation coverage.

**Two findings, and the first is the larger one.**

1. **The ungated 1h Alligator entry is itself negative** — −0.0411R at
   t = −2.56 on 2,677 trades. Strategy 03 recorded the 1h band as
   "inconclusive rather than negative … a statement about those samples' size,
   not a reprieve." That was right. Moving up a timeframe was never an escape
   from the 15m result; it was the same result with a smaller sample.
2. **v3's filters do not rescue it, and appear to hurt.** The gated subset is
   −0.0663R at t = −2.01, *worse* than the −0.0411R it filters from. The same
   pattern as Band 1: the gate discards 82% of trades and does not turn the
   remainder positive.

IWM's gated cell (−0.3214R, t = −2.83 on 42 trades) is the worst in either
band, but at 42 trades it is a curiosity rather than a finding.

## Honest limits

- **Both bands' gated verdicts are convention-sensitive.** Band 1 is t = −2.35
  or −1.81; Band 2 is t = −2.01 or −1.47, depending on whether the signal bar
  is the one before entry or the decision bar itself. Negative under every
  convention, but only decisive under one. The *ungated* Band 2 result
  (t = −2.56) does not depend on the convention at all.
- **Band 2's 4h bars are derived, not cached.** `resample_1h_to_4h.py` is
  validated against the six instruments with a real 4h cache — QQQ and DIA
  reproduce bar for bar (3,520/3,520), and IWM, GLD, SLV and SPY differ only in
  the final bar, where the two caches end at different points. Spot FX has no
  cached 4h anywhere, so its derived bars use the same validated UTC grid but
  have no direct ground truth of their own. Dropping both FX instruments leaves
  the equity-only ungated pool at −0.0471R, t = −2.28 (1,810 trades), so the
  Band 2 conclusion does not rest on the unvalidated FX bars. The equity-only
  gated cell is −0.0711R at t = −1.58.
- **Band 1's pooled verdict is convention-sensitive.** t = −2.35 clears the
  usual bar; t = −1.81 does not. The *direction* is unambiguous under both, but
  this is not the decisive −8.23 that closed Strategy 03. Read it as "the
  premise does not survive", not "falsified with equal force".
- **Filtering costs power.** Band 1 keeps ~120 trades per instrument, below the
  ~150 the project's own budget requires, so per-instrument rows cannot settle
  anything individually and are not offered as if they could.
- **This is a mechanism test, not a Strategy 01 backtest.** It does not model
  macro stance, session windows, jaw-based stops, or v5's ATR buffer. It tests
  the entry premise those versions rest on.
- **This consumed the DIA holdout.** DIA was withheld from the HTF-freshness
  analysis and recorded as unspent. It is included above, so it is now spent in
  an Alligator context. Excluding it changes nothing in Band 1: −0.0665R at
  t = −2.18 (828 trades) under the primary convention, −0.0563R at t = −1.78
  under the alternative. The verdict does not depend on having spent it.

## Verdict

- **v1, v2, v4, v5 — closed.** They rest on a 15-minute Alligator
  mouth-opening entry that loses on 5,600 trades, and their distinguishing
  filters discard 83% of trades without turning it positive. Do not build
  further versions on this entry.
- **v3 — closed.** Moving up a band was not an escape. The 1h Alligator entry
  it rests on is itself negative on 2,677 trades (−0.0411R, t = −2.56), and
  v3's filters leave the remainder at −0.0663R (t = −2.01) — worse than what
  they filter. Strategy 01 has no surviving version.

## Reproduction

```
python scripts/analyze_strategy_01_inheritance.py \
    --data-root <path>/data/market_data/ibkr --band both
```

The bar cache is gitignored, so `--data-root` must point at a local cache. The
Strategy 03 ledgers it reads are tracked.
