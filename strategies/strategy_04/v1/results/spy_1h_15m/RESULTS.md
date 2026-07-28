# Strategy 04 v1 — SPY 1h zones / 15m reaction results

## Run scope

- Data: 34,200 SPY 15-minute bars from 2021-04-14 through 2026-07-16.
- Zone engine: 9,189 SPY one-hour bars from 2021-04-19 through 2026-07-16.
- Candidate reactions: 101.
- Reactions passing the session-entry filter: 44.
- Executed trades after enforcing one open position at a time: 42.
- Entry timing: next 15-minute open after a completed reaction candle.
- Target: 1.0R.
- Fixed risk: 0.15% of current equity.
- RRMS: capped five-loss sequence.

## Result comparison

| Sizing | Trades | Wins | Losses | Win rate | Net P&L | Profit factor | Average R | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed 0.15% | 42 | 23 | 19 | 54.8% | +$308.97 | 1.10 | +0.050R | $934.08 |
| Five-loss RRMS | 42 | 23 | 19 | 54.8% | +$1,842.47 | 1.26 | +0.050R | $2,789.79 |

RRMS reached tier 4. It changed position size, net P&L, and drawdown; it did
not change the entry and exit price path.

## Direction breakdown

| Sizing | Direction | Trades | Wins | Losses | Win rate | Net P&L | Average R |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed | Long | 23 | 8 | 15 | 34.8% | -$1,176.44 | -0.343R |
| Fixed | Short | 19 | 15 | 4 | 78.9% | +$1,485.42 | +0.526R |
| RRMS | Long | 23 | 8 | 15 | 34.8% | -$2,769.06 | -0.343R |
| RRMS | Short | 19 | 15 | 4 | 78.9% | +$4,611.53 | +0.526R |

## Exit and holding behaviour

- Targets: 23.
- Stops: 19.
- Weekend closes: 0.
- Maximum consecutive losses: 4.
- Average holding time: 3.93 hours.
- Fixed total commissions: $46.13.
- RRMS total commissions: $110.84.

## Interpretation

The combined first-pass strategy is slightly profitable after the current
commission and slippage assumptions, but the edge is thin. A fixed profit
factor of 1.10 and average result of +0.05R are not strong enough to authorize
paper or live execution.

The most important finding is the direction asymmetry. Short reactions were
strong while long reactions lost money. This could be a real feature of the
sample, a regime effect, or a weakness in the long reaction definition. It must
be inspected trade by trade before adding filters or changing rules.

The next validation step is visual review of the ten saved charts, with
particular attention to:

1. Whether long entries truly approached demand from above.
2. Whether the one-hour zone was still structurally relevant.
3. Whether overlapping zones selected the intended zone.
4. Whether the 0.05 × one-hour ATR stop buffer is too tight for long setups.
5. Whether the unusually high short win rate survives out-of-sample testing.

## Saved evidence

- [Backtest report](backtest_report.json)
- [Candidate signals](candidate_signals.csv)
- [Fixed-risk trades](fixed_trades.csv)
- [RRMS trades](rrms_trades.csv)
- [Trade-review index](review/trade_charts/index.html)
- [Trade-chart manifest](review/trade_charts/manifest.json)

Historical research only. No live order permission is included.

