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
equity indices, small caps, precious metals and spot FX. This does not rest on
pooling, and it does not rest on any one venue or asset class.

At 1h and 4h the same signal is inconclusive rather than negative (n = 253–318
and 73–76), which is a statement about those samples' size, not a reprieve.

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
