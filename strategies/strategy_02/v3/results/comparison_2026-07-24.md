# Strategy 02 v3 test — 4h confirmation + 1h execution

Historical-only research. Results include the existing cost and slippage model, but exclude real bid/ask spread and execution constraints.

| Instrument | Eligible signals | Realised trades | Win rate | Fixed P&L | Fixed PF | Fixed max DD | RRMS P&L | RRMS PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 6 | 5 | 60.0% | +$111.34 | 1.41 | $150.85 | +$237.75 | 1.88 |
| QQQ / US100 | 7 | 6 | 50.0% | -$5.10 | 0.99 | $292.26 | +$533.90 | 1.83 |
| DIA / US30 proxy | 5 | 4 | 25.0% | -$320.88 | 0.03 | $331.28 | -$580.90 | 0.02 |
| MGC Gold (diagnostic) | 2 | 1 | 0.0% | -$40.36 | 0.00 | $40.36 | -$40.36 | 0.00 |

## Conclusion

The version is too selective for a reliable five-year conclusion: SPY has only five realised trades, QQQ six, and DIA four. SPY is provisionally the best of the three, but the sample is far too small to approve this version for shadow trading. Gold is not comparable because it uses a different futures session, contract economics, and a shorter continuous-history window.
