# Strategy 02 v2 — multi-asset comparison

Historical research only. All runs use the currently implemented Strategy 02
v2 rules: 1-hour reversal confirmation, 15-minute alignment and structure,
time/session rules, Friday close, 1:1 target, and completed 15-minute VIX close
strictly below 20.00.  Data source: locally cached IBKR history.

| Instrument | Usable 15m period | Trades | Win rate | Fixed P&L | Fixed PF | Fixed max DD | RRMS P&L | RRMS PF | RRMS max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | Apr 2021 – Jul 2026 | 26 | 53.8% | +$548.68 | 1.43 | $404.56 | +$1,264.25 | 1.77 | $534.36 |
| QQQ / US100 | Mar 2021 – Jul 2026 | 28 | 46.4% | -$333.36 | 0.82 | $641.31 | +$970.44 | 1.29 | $1,224.27 |
| DIA / US30 proxy | Mar 2021 – Jul 2026 | 30 | 53.3% | +$428.38 | 1.31 | $724.42 | +$871.52 | 1.40 | $940.74 |
| MGC Gold | Apr – Jul 2026 | 1 | 0.0% | -$148.92 | 0.00 | $148.92 | -$148.92 | 0.00 | $148.92 |

## Interpretation

- **SPY** is the best fixed-sizing candidate in this sample.
- **DIA/US30** is positive under both fixed and RRMS sizing, but has a larger
  drawdown than SPY.
- **QQQ/US100** is not viable under fixed sizing in this version. RRMS turns
  its account P&L positive, but the underlying average R remains negative;
  therefore RRMS is masking, not fixing, the signal quality.
- **MGC** is not comparable: one trade is insufficient, and IBKR's continuous
  futures intraday history is too short for a valid multi-year test.

These results exclude commissions, bid/ask spread, and slippage, so they are a
research screen rather than an execution approval.
