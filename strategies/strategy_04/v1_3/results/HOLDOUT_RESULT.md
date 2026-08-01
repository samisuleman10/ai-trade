# Strategy 04 v1.3 — holdout result

Run 30 July 2026, against the decision rule committed in `../strategy.md`
before any result existed (commit `086975a`).

## The method changed, and why

The specification called for a strict chronological holdout. That method was
abandoned before running because it is provably underpowered: the smallest edge
each holdout could detect is larger than the edge being tested.

| Symbol | Holdout trades at 70/30 | Smallest detectable edge | Edge observed |
| --- | ---: | ---: | ---: |
| SPY | 12 | ±0.586R | +0.218R |
| DIA | 15 | ±0.531R | +0.177R |
| QQQ | 18 | ±0.496R | +0.019R |
| EURUSD | 73 | ±0.233R | −0.073R |
| GBPUSD | 78 | ±0.225R | −0.119R |
| FX pooled | 151 | ±0.160R | −0.097R |

Every row needs a larger effect than the one under test. The result would have
been "inconclusive" by construction, telling us about the sample rather than
the strategy. Pooled FX reaches significance only when all 503 trades are used;
splitting it removes the finding.

A **cross-instrument holdout** was used instead. It is a weaker design than a
chronological split in one respect — it cannot detect a strategy that decayed
over time — but it is the only one the data supports.

## Why FX qualifies as a holdout

No filter was ever fitted to FX data, because FX did not exist in the
repository when the filters were written:

| Artifact | First committed |
| --- | --- |
| v1.1 spec, 25% penetration rule | 2026-07-28 22:40 |
| v1.2 spec, Filters A and B | 2026-07-29 10:58 |
| FX downloader | 2026-07-29 23:17 |
| FX baseline runs | 2026-07-30 05:03 |

The 25% rule predates any FX data by 25 hours; v1.2's filters by 12.5 hours.
Filter A's threshold of 2.5 was proposed on 29 July from an equity-only
exploratory split and is recorded in the v1.2 spec as chosen post-hoc on
equities and requiring a sweep. The sweep that later covered FX
(`../../v1_2/results/sweep/risk_ratio_sweep.json`, committed 07:51 on 30 July)
reports eleven thresholds; it does not select one, and the 2.5 default was
already in the implementation committed at 07:24.

All three filters were therefore fixed before any FX result could influence
them.

## Result, evaluated strictly per single symbol

The committed rule judges "any single symbol". Pooled FX is not a single
symbol and is excluded from the verdict, though it is reported below for
context.

| Configuration | Symbol | Trades | Average R | t | Bar | Rule |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| v1.2 A+B | GBPUSD | 148 | −0.2535 | −3.11 | 1.960 | **abandon** |
| v1.2 A | GBPUSD | 231 | −0.1954 | −2.97 | 1.960 | **abandon** |
| v1.2 B | GBPUSD | 175 | −0.1966 | −2.60 | 1.960 | **abandon** |
| v1.2 A+B | EURUSD | 119 | −0.2016 | −2.20 | 1.980 | **abandon** |
| v1.2 B | EURUSD | 141 | −0.1797 | −2.13 | 1.960 | **abandon** |
| v1.1 base | GBPUSD | 260 | −0.1192 | −1.91 | 1.960 | neither |
| v1.2 base | GBPUSD | 260 | −0.1192 | −1.91 | 1.960 | neither |
| v1.2 A | EURUSD | 218 | −0.0928 | −1.37 | 1.960 | neither |
| v1.1 base | EURUSD | 243 | −0.0728 | −1.13 | 1.960 | neither |
| v1.2 base | EURUSD | 243 | −0.0728 | −1.13 | 1.960 | neither |

`t` is compared against Student's two-sided 95% critical value at that run's
own degrees of freedom, per the committed rule.

**The abandon rule fires five times. The accept rule fires zero times.**

For context only, outside the rule: pooled FX at 503 trades gives −0.0968R,
t = −2.16.

## The finding inside the finding

The unfiltered configurations do **not** fire. GBPUSD v1.1 base sits at
t = −1.91 and EURUSD base at −1.13 — both inconclusive.

Every configuration that fires the abandon rule is one with v1.2 filters
applied. Adding filters moves FX from "cannot conclude" to "conclusively
loses", and stacking both filters produces the worst result recorded
(GBPUSD A+B, t = −3.11).

The filters were built to improve the strategy. On instruments they were never
fitted to, they measurably degrade it. That is the clearest evidence yet that
they encode characteristics of the SPY sample they were derived from rather
than a property of the market.

## What this does and does not establish

**Establishes:** on EURUSD and GBPUSD, Strategy 04 with the v1.2 filters loses
money at conventional significance, on data those filters never saw.

**Does not establish:** that the strategy fails on equities. The equity samples
are too small to conclude anything in either direction, which is itself the
finding — 38 SPY trades cannot support a promotion decision, and roughly five
more years of data would be needed to change that.

**Does not establish:** that the underlying zone-reaction idea is worthless.
It establishes that this implementation, with these filters, on these two FX
pairs, loses.

## Caveats

- EURUSD and GBPUSD are both USD crosses and correlated, so the five firing
  runs are not five independent confirmations.
- The v1.2 FX results were examined during dashboard work before this
  evaluation was written. The filters were fixed beforehand, so the holdout
  property holds for them — but FX is no longer pristine for anything designed
  after 30 July 2026. Future filters need a different holdout.
- The risk-ratio sweep now covers FX. If any future threshold is selected using
  those rows, FX ceases to be a holdout for that parameter.
- A cross-instrument holdout cannot detect time-based decay. A chronological
  test remains desirable once trade counts allow one.

## Consequence under the committed rule

The rule states: abandon or fundamentally rethink when out-of-sample average R
is negative with |t| ≥ 2 on any single symbol. That condition is met five
times over, and never met in the accepting direction.

The pre-committed consequence is therefore to **stop adding filters to
Strategy 04** and to treat any further work on it as a fundamental rethink
rather than an extension. Per the decision rule's own third clause, this is not
an invitation to design a sixth filter.


---

# Second holdout: IWM, GLD and SLV

Added 1 August 2026. The evaluation above stands as written on 30 July; this
section extends it to three instruments that did not exist in the repository
when it was written.

## Why these three qualify as a holdout

The same provenance argument that admitted FX:

| Artifact | First committed |
| --- | --- |
| v1.2 spec, Filters A and B | 2026-07-29 10:58 |
| IWM/GLD/SLV backtest runs | 2026-07-31 17:29 (`fa975c3`) |

No filter could have been fitted to instruments the repository did not hold.
IWM, GLD and SLV were added to widen coverage, not to test a hypothesis, which
is why nobody noticed at the time that they had become a second holdout.

## What prompted this

GLD's ablation row carries the largest single filter effect anywhere in the
grid: Filter B turns −$1,333.52 into +$578.52, a +$1,912.04 swing, with the
win rate going 0.417 → 0.632. Read as P&L it is the most encouraging number in
the project. Read under the committed rule it is not a result at all.

## Result, evaluated by the same rule

| Configuration | Symbol | Trades | Average R | t | Bar | Detectable edge | Rule |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| base | GLD | 36 | -0.2483 | -1.52 | 2.030 | ±0.457 | neither |
| a | GLD | 35 | -0.1561 | -0.92 | 2.032 | ±0.475 | neither |
| base | SLV | 34 | -0.1530 | -0.88 | 2.035 | ±0.488 | neither |
| b | SLV | 19 | -0.1611 | -0.67 | 2.101 | ±0.669 | neither |
| ab | SLV | 19 | -0.1611 | -0.67 | 2.101 | ±0.669 | neither |
| b | IWM | 24 | -0.1176 | -0.57 | 2.069 | ±0.582 | neither |
| a | IWM | 45 | -0.0133 | -0.09 | 2.015 | ±0.423 | neither |
| a | SLV | 33 | -0.0108 | -0.06 | 2.037 | ±0.494 | neither |
| ab | IWM | 26 | +0.0419 | +0.21 | 2.060 | ±0.559 | neither |
| base | IWM | 41 | +0.1376 | +0.88 | 2.021 | ±0.438 | neither |
| b | GLD | 19 | +0.2037 | +0.89 | 2.101 | ±0.639 | neither |
| ab | GLD | 19 | +0.2037 | +0.89 | 2.101 | ±0.639 | neither |

`Detectable edge` is the smallest true effect that sample size could resolve at
95% confidence and 80% power. It is reported because the v1.3 method requires
power to be stated alongside outcome.

**Zero of twelve runs fire a rule.** GLD's Filter B row — the one that motivated
this evaluation — reaches t = +0.89 against a bar of 2.101, and its 19 trades
could only have resolved an effect of ±0.639R, more than three times the
+0.204R observed.

## What this adds

- **Filter B's direction is not consistent across instruments it never saw.**
  GLD +0.204R, SLV −0.161R, IWM −0.118R: one positive draw in three, none
  significant. That is what noise looks like.
- **Filter B has now been tested on five instruments no filter was fitted to.**
  It produced two significant losses (EURUSD, GBPUSD) and three inconclusive
  results. It has never produced a significant gain on any instrument, in
  sample or out.
- **The +$1,912 is mostly a bad base, not a good filter.** GLD base is
  −0.248R, the weakest base in the equity set. Filter B discards 17 of its 36
  trades; what remains is not distinguishable from zero.
- **Filter A contributes nothing once B has selected.** GLD `b` and GLD `ab`
  are the identical 19 trades, as are SLV `b` and SLV `ab`.

## Power: this is not confirmable on GLD

Detecting +0.204R at 95% confidence and 80% power needs roughly 186 trades.
GLD's cached history (2021-03-18 to 2026-04-20) yields 19 filtered trades,
about 3.7 per year. Reaching 186 would take on the order of fifty years of
additional data. "Confirm GLD Filter B out of sample" is not a task that can
succeed with this instrument, and should not be carried as an open lead.

## Reproducing the arithmetic

The July evaluation's arithmetic was never committed as code, so it could not
be re-run when new instruments arrived. It now is:

```
python scripts/evaluate_holdout_significance.py     --results strategies/strategy_04/v1_2/results --symbols IWM GLD SLV
```

The script imports nothing from `ai_trade` and reads only `fixed_trades.csv`,
keeping the same independence as the audit rules. Run against EURUSD and
GBPUSD it reproduces the FX table above exactly — same trade counts, same
average R, same t, same five abandons. Its `Bar` column is computed at each
run's own degrees of freedom, so it reads 1.976 where the July table recorded
1.960 from a coarser lookup; no verdict changes.

## Caveats

- GLD, SLV and IWM are **no longer pristine** for anything designed after
  1 August 2026. Their results have now been examined, exactly as happened to
  FX on 30 July. Future filters need a different holdout again.
- GLD and SLV are both precious metals and are correlated; they are not two
  independent confirmations.
- IWM is a US equity index correlated with SPY, QQQ and DIA. It is a weaker
  holdout than FX or metals, because whatever the filters learned from SPY is
  more likely to transfer there for reasons that are not an edge.
- A cross-instrument holdout still cannot detect time-based decay.
