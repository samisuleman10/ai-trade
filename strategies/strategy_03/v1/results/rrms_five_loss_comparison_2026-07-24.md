# Strategy 03 v1 — capped five-loss RRMS comparison

Status: historical research only. No order submission is enabled.

## Locked sizing rule tested

- Sequence: `0.15% → 0.35% → 0.70% → 1.50% → 1.50%`.
- Every negative net exit advances the sequence, including a losing Friday/weekend close.
- Any profitable exit resets the next trade to `0.15%`.
- After the fifth consecutive loss, the next trade resets to `0.15%`.
- The sequence carries across weeks; there is no weekly reset.

## Four-hour results

| Symbol | Trades | W/L | Fixed P&L | Fixed PF | Fixed max DD | Five-loss RRMS P&L | RRMS PF | RRMS max DD | Max tier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 73 | 39/34 | -$1,117.89 | 0.72 | $1,215.59 | +$2,130.15 | 1.30 | $1,517.97 | 4 |
| QQQ | 75 | 35/40 | -$1,022.04 | 0.71 | $1,279.53 | -$4,623.59 | 0.54 | $5,213.72 | 4 |
| DIA | 76 | 41/35 | -$617.00 | 0.84 | $1,665.07 | -$0.46 | 1.00 | $1,821.15 | 4 |

## Trade anatomy

| Symbol | Long W/L | Short W/L | Weekend exits W/L | Stops / targets |
|---|---:|---:|---:|---:|
| SPY | 24/18 | 15/16 | 30/11 | 23 / 9 |
| QQQ | 23/24 | 12/16 | 25/23 | 17 / 10 |
| DIA | 31/14 | 10/21 | 27/14 | 21 / 14 |

## Interpretation

- SPY benefits from the order of wins and losses in this sample, but its fixed-risk result is still negative. The sizing progression changes dollar outcomes; it does not change the underlying trade expectancy.
- QQQ shows the main danger: loss escalation turns a fixed loss of about `$1.0k` into about `$4.6k` and increases maximum drawdown above `$5.2k`.
- DIA reaches approximately break-even under RRMS, but fixed-risk performance remains negative.
- Because all three fixed-risk profit factors remain below `1.0`, this RRMS rule should remain a research comparison rather than an execution rule.

Ten representative price charts and interactive fixed/RRMS ledgers are saved inside each symbol's `review` folder.
