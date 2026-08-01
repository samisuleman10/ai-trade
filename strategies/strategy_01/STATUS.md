# Strategy 01 — status

**Closed for v1, v2, v4 and v5. v3 remains open.** Recorded 1 August 2026.

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
the Lips. v3 is not: it moves the whole structure up a band.

## The test

`scripts/analyze_strategy_01_inheritance.py` re-labels Strategy 03's recorded
15-minute trades with Strategy 01's two extra conditions, using Strategy 01's
own definitions imported from `ai_trade.strategy_01` rather than
reimplemented. It asks one question: **do those filters rescue an entry that
loses without them?**

The signal bar is the completed bar before entry. Because that convention
matters, both it and the alternative are reported.

Validity check: the unfiltered column reproduces the published Strategy 03
figures exactly — 5,602 trades, −0.1033R, t = −8.23, with zero unmatched
trades.

## Result — the filters do not rescue the entry

Signal = bar before `decision_timestamp`:

| Instrument | All n | All R | All t | S01-gated n | S01-gated R | S01-gated t |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 797 | −0.0954 | −2.77 | 122 | −0.0848 | −0.99 |
| QQQ | 805 | −0.0867 | −2.54 | 120 | −0.0268 | −0.30 |
| DIA | 806 | −0.0910 | −2.63 | 136 | −0.0683 | −0.86 |
| IWM | 834 | −0.1236 | −3.70 | 126 | −0.1364 | −1.62 |
| GLD | 725 | −0.1127 | −3.19 | 114 | **+0.0502** | +0.58 |
| SLV | 734 | −0.1654 | −4.59 | 120 | −0.1090 | −1.35 |
| EURUSD | 414 | −0.0896 | −2.49 | 98 | −0.1417 | −2.07 |
| GBPUSD | 487 | −0.0336 | −0.93 | 126 | −0.0238 | −0.37 |
| **Pooled** | **5,602** | **−0.1033** | **−8.23** | **962** | **−0.0668** | **−2.35** |

The gate keeps 17.2% of trades. Under the alternative convention it keeps
15.8% and the gated pool is −0.0536R at t = −1.81.

**The filters help, and not enough.** They lift the pooled result from
−0.1033R to −0.0668R — a real improvement, and still a losing configuration.
Every instrument except GLD stays negative, GLD's positive figure is noise at
t = +0.58, and no per-instrument gated result reaches significance in the
favourable direction. There is no subset here that makes money.

## Honest limits on this conclusion

- **The pooled verdict is convention-sensitive.** t = −2.35 clears the usual
  bar; t = −1.81 does not. The *direction* is unambiguous under both, but this
  is not the decisive −8.23 that closed Strategy 03. Read it as "the premise
  does not survive", not "falsified with equal force".
- **Filtering costs power.** 962 trades pooled, ~120 per instrument — below the
  ~150 the project's own power budget requires. Per-instrument results here
  cannot settle anything individually and are not offered as if they could.
- **This is a mechanism test, not a Strategy 01 backtest.** It does not model
  macro stance, session windows, jaw-based stops, or v5's ATR buffer. It tests
  the entry premise those versions rest on.
- **v3 is untested by this.** It enters on 1h with 4h confirmation, and
  Strategy 03 is *inconclusive* at 1h/4h — which is a sample-size statement,
  not a reprieve. v3 needs its own measurement before any verdict.
- **This consumed the DIA holdout.** DIA was withheld from the HTF-freshness
  analysis and recorded as unspent. It is included above, so it is now spent
  in an Alligator context. Excluding it changes nothing: the gated pool is
  −0.0666R at t = −2.18 (826 trades) under the primary convention and −0.0563R
  at t = −1.78 under the alternative, against −0.0668/−2.35 and −0.0536/−1.81
  with DIA included. The verdict does not depend on having spent it.

## Verdict

- **v1, v2, v4, v5 — closed.** They rest on a 15-minute Alligator mouth-opening
  entry that loses on 5,602 trades, and their distinguishing filters discard
  83% of trades without turning it positive. Do not build further versions on
  this entry.
- **v3 — open, and the only part worth measuring.** It is the one version that
  is not a 15-minute entry. If Strategy 01 has anything left, it is there.

## Reproduction

```
python scripts/analyze_strategy_01_inheritance.py --data-root <path>/data/market_data/ibkr
```

The bar cache is gitignored, so `--data-root` must point at a local cache. The
Strategy 03 ledgers it reads are tracked.
