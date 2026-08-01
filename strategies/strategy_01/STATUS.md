# Strategy 01 — status

**v1, v2, v4, v5 are closed. v3 is unresolved — measured, and the measurement
returned nothing.** Recorded 1 August 2026.

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
where Strategy 03 is inconclusive rather than falsified.

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

## Band 2: v3 — no information either way

Signal = bar before `decision_timestamp`; 4h confirmation over a 1h entry:

| Instrument | Covered n | R | t | Gated n | Gated R | Gated t | Dropped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 100 | −0.0347 | −0.37 | 16 | +0.0437 | +0.21 | 153 |
| QQQ | 294 | −0.0137 | −0.27 | 51 | −0.0666 | −0.61 | 0 |
| DIA | 317 | −0.0356 | −0.71 | 53 | +0.0210 | +0.20 | 1 |
| **Pooled** | **711** | **−0.0264** | **−0.79** | **120** | **−0.0132** | **−0.19** | **154** |

Under the alternative convention the gated pool is 114 trades at **+0.0200R,
t = +0.28** — the sign flips, which is what a t of ±0.2 means in practice.

**This does not close v3 and does not support it.** Every figure is
indistinguishable from zero. The ungated 1h entry is −0.0264R at t = −0.79;
the gated subset is −0.0132R at t = −0.19. Nothing here is evidence of
anything.

Why the measurement is empty:

- **Only three instruments have a 1h ledger** — SPY, QQQ, DIA. The five
  instruments added on 2026-08-01 were backtested at 15m only.
- **SPY loses 153 of 253 trades** to coverage: its 4h cache spans two years
  against a five-year ledger. SPY contributes 16 gated trades.
- **120 gated trades pooled**, against a power budget of ~150 *per instrument*.
  This is roughly an eighth of the evidence the 15m band had.

## Honest limits

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
- **v3 — unresolved, and cheap to resolve.** It is the one version not built on
  the falsified 15m entry, and the only reason it is unresolved is missing
  data, not an adverse result. Settling it needs 1h Strategy 03 ledgers for
  IWM, GLD, SLV, EURUSD and GBPUSD, and a five-year 4h SPY cache. That is a
  backtest run, not new research. Until then v3 is neither supported nor
  refuted, and nothing should be built on it.

## Reproduction

```
python scripts/analyze_strategy_01_inheritance.py \
    --data-root <path>/data/market_data/ibkr --band both
```

The bar cache is gitignored, so `--data-root` must point at a local cache. The
Strategy 03 ledgers it reads are tracked.
