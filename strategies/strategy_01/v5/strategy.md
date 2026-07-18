---
id: strategy_01_v5_dynamic_atr_jaw_buffer
name: Multi-Timeframe Alligator with Dynamic ATR Jaw Buffer
version: 0.5.0
status: two_year_preliminary_backtest_not_validated
execution_mode: historical_research_only
primary_instrument: SPY
owner: Sami
last_updated: 2026-07-17
---

# Strategy 01 v5: Dynamic ATR Jaw Buffer

V5 inherits V4's completed 1-hour trend, 15-minute entry, and 5-minute
momentum alignment; long/short transition trigger; 1R target; RRMS; and SPY
session/weekend rules. It changes **one parameter only**: the stop buffer.

| Rule | V4 | V5 |
| --- | --- | --- |
| Long stop | 0.05% below 15m Jaw | `max($0.01, 0.10 × completed 15m ATR(14))` below Jaw |
| Short stop | 0.05% above 15m Jaw | `max($0.01, 0.10 × completed 15m ATR(14))` above Jaw |

ATR is Wilder-smoothed and uses only completed 15-minute bars. The $0.01 floor
is SPY's minimum price increment. Position sizing remains risk-based, so a
wider dynamic stop produces fewer shares rather than a larger planned loss.

This is a comparison experiment, not a validated strategy. It must be tested
on exactly the saved V4 data before any further decision.

## Two-year preliminary comparison — 2026-07-17

V5 used the same saved SPY cache and cost/session assumptions as V4. The only
change was the dynamic ATR Jaw buffer.

| Measure | V4 fixed buffer | V5 dynamic buffer |
| --- | ---: | ---: |
| Completed fixed-risk trades | 42 | 44 |
| Win rate | 47.6% | 56.8% |
| Net P&L on $100,000 | -$675.42 | +$388.58 |
| Profit factor | 0.78 | 1.14 |
| Average R | -0.106R | +0.060R |
| Maximum drawdown | $1,185.36 | $719.38 |
| Long / short trades | 34 / 8 | 36 / 8 |

The V5 RRMS overlay returned +$2,595.31 with a 1.45 profit factor, but it also
increased maximum drawdown to $1,255.38. The fixed-risk result is the primary
signal of strategy quality.

V5 is promising but **not validated**: the sample is 44 trades, the fixed-risk
profit factor is only 1.14, and no macro filter has yet been applied. It must
remain historical research only. The saved fixed-trade visual review is at
`outputs/strategy_01/v5/spy/two_year_preliminary_2026-07-17/trade_review.html`.

## Five-year robustness check — 2026-07-17

The same cached SPY dataset was extended without redownloading existing bars:
97,920 five-minute, 34,200 fifteen-minute, and 9,189 one-hour bars, reaching
at least 9 July 2021 in the lower timeframes. This is a more useful test of
whether the two-year result survives other market conditions.

| Measure | Fixed 0.15% risk | RRMS with tier-4 reset |
| --- | ---: | ---: |
| Completed trades | 125 | 125 |
| Win rate | 50.4% | 50.4% |
| Net P&L on $100,000 | -$1,073.92 | -$1,538.91 |
| Profit factor | 0.88 | 0.93 |
| Average R | -0.056R | -0.056R |
| Maximum drawdown | $3,263.89 | $8,292.90 |
| Long / short trades | 84 / 41 | 84 / 41 |

This five-year result overturns the initial two-year promise: V5 does not yet
show a durable positive fixed-risk expectancy. The RRMS tier-4 reset is now
implemented for V5 exactly as specified; its greater drawdown makes it less
attractive here. V5 must remain historical research only and must not be added
to the shadow scheduler.
