---
id: strategy_01_v3_dia_dow_30_proxy
name: Bill Williams Alligator + Heikin Ashi + RRMS — v3 / DIA
version: 0.3.0
status: preliminary_historical_research
execution_mode: historical_backtest_only
market: Dow Jones Industrial Average proxy
research_instrument: DIA
owner: Sami
last_updated: 2026-07-16
---

# Strategy 01 v3: Dow 30 / DIA

This is an **out-of-sample instrument test** of locked SPY Strategy 01 v3. It
does not change the strategy, its risk ladder, or its time windows.

## Instrument decision

The target market is the Dow Jones Industrial Average (commonly “US 30” or
“Dow 30”). The research instrument is **DIA**, the liquid Dow 30 ETF proxy.
This is not a CFD or futures test; those instruments require their own contract
sizing, fees, session, and rollover model.

## Inherited rules

All rules are inherited unchanged from
`strategies/strategy_01/v3/spy/strategy.md`: manual bullish macro regime and
long only; completed 4-hour confirmation plus 1-hour entry; no first/final-hour
or Friday entries; weeknight holds; Friday force close; 0.15% initial account
risk and the four-step RRMS ladder.

## Research objective

Measure whether the unchanged strategy transfers to DIA using the same two-year
historical test. Compare trade count, win rate, profit factor, average R,
drawdown, and the visual trade review against SPY and QQQ. Results are
historical evidence only and never authorise paper or live execution.

## First two-year result — 2026-07-16

**Data:** IBKR regular-session DIA bars, 17 Jul 2024 through 16 Jul 2026;
3,492 one-hour bars and 1,167 four-hour bars. The validation reports show no
duplicates or invalid OHLC rows.

| Measure | Fixed risk | RRMS ladder |
| --- | ---: | ---: |
| Raw candidates / eligible signals | 47 / 20 | 47 / 20 |
| Completed trades | 17 | 17 |
| Wins / losses | 7 / 10 | 7 / 10 |
| Win rate | 41.2% | 41.2% |
| Net P&L on $100,000 starting equity | -$202.74 | +$222.34 |
| Profit factor | 0.80 | 1.14 |
| Average R | -0.084R | -0.084R |
| Maximum drawdown | $503.29 | $747.40 |
| Exits: stop / target / Friday close | 6 / 5 / 6 | 6 / 5 / 6 |

The RRMS ladder made the dollar P&L positive because its risk was larger during
some later winning recovery trades. It did **not** improve the underlying trade
quality: the win rate and average R are the same, and drawdown increased.
Seventeen trades is far too small to validate this as an edge. DIA remains
historical research only; it must not move to paper or live trading. The
reproducible run, chart, input data, source snapshot, and hashes are archived
under `docs/strategy_01/v3/dia/pipeline_archives/two_year_preliminary_2026-07-16/`.
