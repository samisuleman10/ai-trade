# Strategy 04 v1.1 — RRMS policy

## Locked cycle for future RRMS experiments

| Consecutive negative exits before entry | Risk for the next trade |
| ---: | ---: |
| 0 | 0.15% |
| 1 | 0.35% |
| 2 | 0.70% |
| 3 | 1.50% |

After the fourth consecutive negative exit, the next trade resets to 0.15%.
A profitable exit also resets the next trade to 0.15%. Negative Friday forced
closes count as losses.

This replaces the previous research proposal that allowed a fifth 1.50% loss.
It is a sizing policy, not a signal-quality improvement: it reduces damage in
long losing streaks but cannot create an edge where the fixed-risk strategy is
near flat or negative.

## Evidence

On the Strategy 04 v1.1 QQQ replay, the four-loss reset improved RRMS P&L from
-$993.83 to -$663.73 and reduced maximum drawdown from $7,234.14 to $5,848.64.
SPY and DIA were unchanged because neither experienced four consecutive losses.
