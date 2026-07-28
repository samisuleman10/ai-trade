# Strategy 03 v1 — 4-hour test

Historical research using locally cached IBKR regular-session 4-hour bars. The shortened opening segment uses its observed next same-session bar as the causal decision/entry boundary. Results include the standard timing rules, Friday close, commission, and slippage assumptions.

| Instrument | Trades | Win rate | Net P&L | Profit factor | Average R | Max drawdown | RRMS P&L | Weekend exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 73 | 53.4% | -$1,117.89 | 0.72 | -0.101 | $1,215.59 | +$1,432.96 | 41 |
| QQQ / US100 | 75 | 46.7% | -$1,022.04 | 0.71 | -0.098 | $1,279.53 | -$1,770.23 | 48 |
| DIA / US30 | 76 | 53.9% | -$617.00 | 0.84 | -0.054 | $1,665.07 | +$537.08 | 41 |

## Interpretation

Fixed sizing is negative for every instrument, so the raw 4-hour mouth-opening signal does not show a positive edge. SPY and DIA have win rates above 50%, but more than half of their positions exit at the Friday close rather than at the 1R target or stop. These partial outcomes make win rate misleading. Positive RRMS results for SPY and DIA come from changing risk after losses while the underlying average R remains negative; they do not validate the signal.
