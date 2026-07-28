# Strategy 03 v1 — detailed 4-hour interpretation

## Performance

| Instrument | Sizing | Trades | W/L | Win rate | Net P&L | PF | Avg R | Max DD | Max loss streak |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | Fixed 0.15% | 73 | 39/34 | 53.4% | -$1,117.89 | 0.72 | -0.101 | $1,215.59 | 4 |
| SPY | RRMS | 73 | 39/34 | 53.4% | +$1,432.96 | 1.23 | -0.101 | $1,447.48 | 4 |
| QQQ / US100 | Fixed 0.15% | 75 | 35/40 | 46.7% | -$1,022.04 | 0.71 | -0.098 | $1,279.53 | 6 |
| QQQ / US100 | RRMS | 75 | 35/40 | 46.7% | -$1,770.23 | 0.73 | -0.098 | $3,459.59 | 6 |
| DIA / US30 | Fixed 0.15% | 76 | 41/35 | 53.9% | -$617.00 | 0.84 | -0.054 | $1,665.07 | 4 |
| DIA / US30 | RRMS | 76 | 41/35 | 53.9% | +$537.08 | 1.09 | -0.054 | $1,802.89 | 4 |

## Direction and exit anatomy

| Instrument | Sizing | Long W/L | Long P&L | Short W/L | Short P&L | Weekend exits W/L | Weekend P&L | Stops | Targets |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | Fixed 0.15% | 24/18 | -$105.96 | 15/16 | -$1,011.94 | 41 (30/11) | +$1,055.35 | 23 | 9 |
| SPY | RRMS | 24/18 | +$2,410.05 | 15/16 | -$977.09 | 41 (30/11) | +$2,014.27 | 23 | 9 |
| QQQ / US100 | Fixed 0.15% | 23/24 | -$306.91 | 12/16 | -$715.14 | 48 (25/23) | +$13.29 | 17 | 10 |
| QQQ / US100 | RRMS | 23/24 | -$575.06 | 12/16 | -$1,195.17 | 48 (25/23) | -$1,049.69 | 17 | 10 |
| DIA / US30 | Fixed 0.15% | 31/14 | +$391.28 | 10/21 | -$1,008.27 | 41 (27/14) | +$680.24 | 21 | 14 |
| DIA / US30 | RRMS | 31/14 | +$356.38 | 10/21 | +$180.70 | 41 (27/14) | +$639.74 | 21 | 14 |

Average holding time was 54.8 hours for SPY, 54.7 hours for QQQ, and 47.4 hours for DIA. Each RRMS run reached tier 3.

## Interpretation

1. **The weekend rule is not the main problem.** Under fixed sizing, weekend closures contributed +$1,055 for SPY, +$13 for QQQ, and +$680 for DIA. Closing before the weekend protected the system rather than causing the overall losses in this sample.
2. **Short entries are the clearest weakness.** Fixed-risk shorts lost about $1,012 on SPY, $715 on QQQ, and $1,008 on DIA. DIA longs were genuinely positive, while SPY longs were nearly flat and QQQ longs remained negative.
3. **RRMS changes the outcome without changing signal quality.** SPY and DIA become profitable under RRMS even though their fixed-sizing average R stays negative. The gain depends on which trades receive larger risk after losses and therefore is sequence-sensitive.
4. **Win rate is insufficient.** SPY and DIA win more than half their trades but still lose under equal fixed risk because the distribution of stop, target, and partial weekend outcomes is unfavorable.
5. **Best next hypothesis:** retain the simple Alligator opening rule but test long-only entries when the macro regime is bullish. DIA provides the strongest evidence for that direction; QQQ does not yet support it.
