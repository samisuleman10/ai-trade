# Strategy 03 Current Status

**The Alligator mouth-opening entry is falsified at 15 minutes.** Historical
research only; not approved for shadow, paper, or live trading.

Recorded 1 August 2026, after the signal was backtested on five further
instruments to test a proposed fix. It is the most strongly evidenced result in
this repository.

## Result

Fixed 0.15% risk, 1:1 target, the v1 rules unchanged. Scored with
`scripts/evaluate_holdout_significance.py`.

| Run | Trades | Avg R | t | Rule |
| --- | ---: | ---: | ---: | --- |
| SLV 15m | 734 | −0.1654 | −4.59 | **abandon** |
| IWM 15m | 834 | −0.1236 | −3.70 | **abandon** |
| GLD 15m | 725 | −0.1127 | −3.19 | **abandon** |
| SPY 15m | 797 | −0.0954 | −2.77 | **abandon** |
| DIA 15m | 806 | −0.0910 | −2.63 | **abandon** |
| QQQ 15m | 805 | −0.0867 | −2.54 | **abandon** |
| EURUSD 15m | 414 | −0.0896 | −2.49 | **abandon** |
| GBPUSD 15m | 487 | −0.0336 | −0.93 | neither |
| **Pooled** | **5,602** | **−0.1033** | **−8.23** | **abandon** |

**Seven of eight instruments fire the abandon rule independently**, across US
equity indices, small caps, precious metals and spot FX.

### How much of this is the intrabar collision assumption

The engine resolves a bar touching both stop and target by taking the stop.
With this strategy's tight bracket (Jaw ± 0.10 ATR) that could matter, so it
was measured: `python scripts/analyze_bracket_collisions.py`.

Collisions are rare — 1.1% to 2.5% of trades, 2.3% to 5.1% of stop exits, and
**zero on both FX pairs**. Re-pricing every one of them as a target fill gives
an optimistic bound:

| | Pooled avg R | t | Rule |
| --- | ---: | ---: | --- |
| As committed (stop first) | −0.1033 | −8.23 | **abandon** |
| Optimistic bound (target first) | −0.0743 | −5.90 | **abandon** |

**The pooled conclusion does not rest on the assumption.** The true value lies
between these and nearer the pessimistic end, and both ends are decisive.

**The per-instrument claim is weaker than it looks, though.** Under the
optimistic bound only four instruments still fire — SLV (−4.37), IWM (−2.77),
EURUSD (−2.49) and GLD (−2.23). The three US equity indices drop below the bar:
SPY −1.90, DIA −1.57, and QQQ falls all the way from −2.54 to **−0.58**, having
had 20 collisions in 805 trades. So "seven of eight independently" holds under
the committed model but not under the alternative; "four of eight, plus a
decisive pooled result" is the claim that survives either way.

Strategy 04 v1.2's base runs were checked the same way and have essentially no
collisions (2 in 760 trades, both GBPUSD), so nothing in
`strategies/strategy_04/STATUS.md` depends on this. Its stops sit at zone
boundaries rather than a fraction of ATR, so its brackets are far wider.

At 1h and 4h the same signal was inconclusive rather than negative (n = 253–318
and 73–76), which was a statement about those samples' size, not a reprieve.

**Update, 1 August 2026 — the 1h band now resolves negative.** That prediction
held. 1h ledgers were generated for the five instruments that only had 15m runs
(IWM, GLD, SLV, EURUSD, GBPUSD), taking the 1h sample from 865 trades on three
instruments to **2,677 on eight**. Pooled: **−0.0411R, t = −2.56**. The 1h
entry is not a reprieve from the 15m result; it is the same result with less
leverage, and it only looked survivable because nobody had run the other five
instruments. See
`strategies/strategy_01/STATUS.md` for the analysis and the per-instrument
table.

**Update, 1 August 2026 — the 4h band does not resolve, and the effect shrank
when the sample doubled.** 4h ledgers were generated for IWM, GLD and SLV from
bars built by `scripts/resample_1h_to_4h.py`, taking the band from three
instruments to six.

| | SPY | QQQ | DIA | IWM | GLD | SLV | Pooled |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| n | 73 | 75 | 76 | 71 | 65 | 88 | **448** |
| R | −0.1005 | −0.0977 | −0.0541 | **+0.0228** | **+0.0001** | −0.0468 | **−0.0475** |
| t | −1.16 | −1.26 | −0.61 | +0.24 | +0.00 | −0.58 | **−1.36** |

Doubling the sample made the result *weaker*, not stronger: the three original
instruments pooled to −0.0838R at t = −1.72, and adding three more moved that
to −0.0475R at t = −1.36. The added instruments are the least negative of the
six. Whatever the earlier figure looked like it was approaching, the fuller
sample does not support it.

**This band cannot be closed with the data that exists.** At the observed
effect and dispersion, |t| = 2 needs roughly **975 trades** against the 448
available. The only remaining sources of power are more equity history, or spot
FX — and FX cannot be run through this band, because
`ai_trade.strategy_03_v1_4h` is an RTH-session adapter that skips signals
crossing an Eastern-date boundary. That logic is meaningless for a 24-hour
market, so adapting it is a separate piece of work rather than a flag.

What can be said: the 4h point estimate (−0.0475R) sits between the 15m
(−0.1033R) and 1h (−0.0411R) results and is negative, so nothing here suggests
4h escapes the pattern. But 4h alone does not carry a verdict, and it should
not be quoted as if it does.

**Consistency check on the derived bars.** Re-running SPY, QQQ and DIA from
derived 4h bars reproduces the committed QQQ and DIA ledgers *exactly*
(75 and 76 trades, identical rows). SPY differs — 66 trades against 73 —
because its committed 4h run starts 2020-07 while its 1h cache, the source for
the derived bars, only starts 2021-04. That is a coverage difference, not a
method difference, and the committed SPY ledger is the one used above.

## The fix that was tested and failed

`docs/Notes/ideas/htf_alligator_confluence_entry_timing.md` proposed that the
entries lose because they arrive late in an extended higher-timeframe move, and
that requiring a freshly-opened HTF Alligator would fix it. Tested on recorded
trades before any strategy was built:

- On SPY and QQQ the gradient looked real: r = −0.113, p = 0.054, five age
  buckets falling monotonically.
- Across seven instruments it vanished: r = −0.029, p = 0.36, with three of the
  five new instruments pointing the wrong way.
- **No HTF state rescues the entry.** Agreeing −0.0715R (t = −2.51), opposing
  −0.1097R (t = −3.07), mouth closed −0.1154R (t = −6.84). The best available
  condition still loses significantly.

## What this costs elsewhere

Strategy 01 is built on the same Alligator indicator. This result does not
directly transfer — Strategy 01 v1 pairs it with Heikin Ashi and a different
entry, and v3 adds a 4h regime — but any Strategy 01 work should begin by
asking whether its entry inherits this.

## Notes for anyone re-running this

- The five new instruments (IWM, GLD, SLV, EURUSD, GBPUSD) were generated on
  2026-08-01 with the committed runner; FX uses the shared spot-FX preset
  (`fx_config.fx_backtest_config`), the same one Strategy 04's FX runs use.
- **DIA was withheld from the mechanism analysis and never read**, so it is
  still available as a holdout. The baseline number above predates that reserve
  and was already committed.
- The committed `fixed_summary.json` and `backtest_report.json` for the
  original SPY/QQQ/DIA runs no longer reproduce exactly: the reports predate two
  `BacktestConfig` fields, and two totals differ in the last float digit. The
  trade ledgers reproduce byte for byte, so the results stand. Strategy 03 has
  no reproduction gate of the kind Strategy 04 has; that is why the drift went
  unnoticed.

## Evidence

- `v1/results/*/fixed_trades.csv` — the ledgers, eight instruments
- `scripts/analyze_htf_alligator_age.py` — the mechanism test
- `scripts/evaluate_holdout_significance.py` — the decision rule as code
