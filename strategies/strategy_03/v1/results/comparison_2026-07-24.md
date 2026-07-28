# Strategy 03 v1 — 15m versus 1h comparison

Historical research using locally cached IBKR regular-session bars. The primary results below use fixed 0.15% account risk per trade and include the existing commission/slippage model.

| Instrument | Timeframe | Trades | Win rate | Net P&L | Profit factor | Average R | Max drawdown | RRMS P&L |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SPY | 15m | 797 | 47.8% | -$10,746.94 | 0.81 | -0.095 | $12,361.46 | -$2,587.79 |
| SPY | 1h | 253 | 53.0% | -$92.11 | 0.99 | -0.001 | $2,248.12 | -$1,568.07 |
| QQQ / US100 | 15m | 805 | 48.1% | -$9,919.95 | 0.83 | -0.087 | $11,199.50 | -$1,356.37 |
| QQQ / US100 | 1h | 294 | 50.7% | -$668.75 | 0.96 | -0.014 | $1,893.73 | -$2,068.60 |
| DIA / US30 | 15m | 806 | 47.9% | -$10,403.64 | 0.83 | -0.091 | $10,796.93 | -$1,636.45 |
| DIA / US30 | 1h | 318 | 51.6% | -$1,562.61 | 0.92 | -0.032 | $3,443.68 | -$3,042.26 |

## Conclusion

The unfiltered 15-minute rule overtrades and has negative expectancy on all three ETFs. The 1-hour version reduces noise substantially, but none of the instruments achieves a fixed-sizing profit factor above 1. SPY 1h is closest to breakeven and is the only reasonable foundation for a later filtered version; Strategy 03 v1 itself is not suitable for shadow trading.
