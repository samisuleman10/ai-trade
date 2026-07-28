# Strategy 03 v1 4h — RRMS weekly-reset test

Weekly-reset rule: every new ISO trading week and every Friday forced close starts the next sequence at 0.15%. A tier-3 stop blocks entries only for the rest of that week.

| Symbol | Fixed P&L / PF / DD | Original RRMS P&L / PF / DD | Weekly-reset RRMS P&L / PF / DD | Original max tier | Weekly max tier |
|---|---|---|---|---:|---:|
| SPY | -$1,117.89 / 0.72 / $1,215.59 | +$1,432.96 / 1.23 / $1,447.48 | -$1,596.39 / 0.64 / $1,698.34 | 3 | 1 |
| QQQ / US100 | -$1,022.04 / 0.71 / $1,279.53 | -$1,770.23 / 0.73 / $3,459.59 | -$1,022.04 / 0.71 / $1,279.53 | 3 | 0 |
| DIA / US30 | -$617.00 / 0.84 / $1,665.07 | +$537.08 / 1.09 / $1,802.89 | -$691.86 / 0.83 / $1,739.93 | 3 | 1 |

## Weekly-reset trade anatomy

| Symbol | W/L | Long P&L | Short P&L | Weekend P&L | Max loss streak |
|---|---:|---:|---:|---:|---:|
| SPY | 39/34 | -$592.11 | -$1,004.28 | +$995.23 | 4 |
| QQQ / US100 | 35/40 | -$306.91 | -$715.14 | +$13.29 | 6 |
| DIA / US30 | 41/35 | +$315.96 | -$1,007.82 | +$604.73 | 4 |

## Interpretation

1. Weekly reset sharply reduces tier carryover: maximum exposure fell from tier 3 to tier 0–1.
2. QQQ improved relative to original RRMS and its drawdown fell by about $2,180, but the result simply returned to the already-negative fixed-risk outcome.
3. SPY and DIA lost the positive P&L produced by original RRMS. This demonstrates that those profits depended on carrying elevated tiers across weeks and landing them on a favorable historical sequence.
4. The weekly-reset rule is safer and easier to control, but it does not create a trading edge. Strategy 03 remains negative under fixed risk and weekly-reset RRMS.
5. RRMS should not be used to approve this strategy. Improve the entry signal first; then evaluate sizing on an independently positive fixed-risk system.
