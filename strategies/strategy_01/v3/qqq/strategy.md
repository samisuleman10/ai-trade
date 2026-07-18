---
id: strategy_01_v3_qqq_nasdaq_100_proxy
name: Bill Williams Alligator + Heikin Ashi + RRMS — v3 / QQQ
version: 0.3.0
status: preliminary_historical_research
execution_mode: historical_backtest_only
market: Nasdaq-100 proxy
research_instrument: QQQ
owner: Sami
last_updated: 2026-07-16
---

# Strategy 01 v3: Nasdaq-100 / QQQ

This is an **out-of-sample instrument test** of the locked SPY Strategy 01 v3
rules. It is not a new strategy and it does not change any entry, exit, risk,
or time-window rule.

## Instrument decision

The target market is the Nasdaq-100 (often called “Nas 100”). The research
instrument is **QQQ**, the liquid Nasdaq-100 ETF. QQQ gives us clean,
regular-session intraday bars and is a tradeable ETF proxy. This is not a
Nasdaq-100 CFD or a futures test; those need their own sizing, fees, session,
and rollover model before their results can be compared.

## Inherited rules

All rules are inherited unchanged from the locked SPY specification at
`strategies/strategy_01/v3/spy/strategy.md`:

- Manual `bullish` macro regime; long only.
- Completed 4-hour Alligator background filter and completed 1-hour entry.
- No entry in the first or final regular-session hour; no Friday entries.
- Weeknight holds allowed; force-close before the weekend.
- 0.15% account-risk sizing, with the same fixed-risk comparison.

## Research objective

Run the identical two-year historical test and compare trade count, win rate,
profit factor, average R, drawdown, and trade-review chart against SPY. A
positive QQQ result is evidence only; it does not authorise paper or live
trading.

## First two-year result — 2026-07-16

**Data:** IBKR regular-session QQQ bars, 17 Jul 2024 through 16 Jul 2026;
3,491 one-hour bars and 1,167 four-hour bars. The data-validation reports show
no duplicates or invalid OHLC rows.

| Measure | Fixed-risk result |
| --- | ---: |
| Raw candidates / eligible signals | 51 / 24 |
| Completed trades | 21 |
| Wins / losses | 8 / 13 |
| Win rate | 38.1% |
| Net P&L on $100,000 starting equity | -$677.55 |
| Profit factor | 0.49 |
| Average R | -0.216R |
| Maximum drawdown | $1,155.85 |
| Exits: stop / target / Friday close | 8 / 3 / 10 |

The RRMS overlay also lost money (13 trades, 23.1% win rate, -$2,925.02,
profit factor 0.13). Therefore Strategy 01 v3 is **not validated for QQQ** and
must not move to paper or live trading on the Nasdaq-100. The complete
reproducible run, chart, input data, source snapshot, and hashes are archived
under `docs/strategy_01/v3/qqq/pipeline_archives/two_year_preliminary_2026-07-16/`.
