---
id: strategy_01_v4_multi_timeframe_alligator
name: Multi-Timeframe Williams Alligator Confirmation
version: 0.4.0
status: two_year_preliminary_backtest_not_validated
execution_mode: historical_research_only
primary_instrument: SPY
market: US equity ETF
direction: long_and_short_alignment
trend_timeframe: 1h
execution_timeframe: 15m
momentum_timeframe: 5m
owner: Sami
last_updated: 2026-07-17
---

# Strategy 01 v4: Multi-Timeframe Alligator Confirmation

## Purpose

Strategy 01 v4 is a separate hypothesis from v3. It trades the 15-minute chart
only when the Williams Alligator is aligned across the 1-hour, 15-minute, and
5-minute timeframes. The 1-hour chart provides the primary trend, the 5-minute
chart confirms short-term momentum, and the 15-minute chart supplies the entry.

The no-lookahead multi-timeframe signal engine and initial long/short backtest
are implemented locally. It has not been validated, paper-traded, or authorised
to submit orders.

## Timeframe roles

| Timeframe | Role | Data rule |
| --- | --- | --- |
| 1 hour | Main trend confirmation | Latest completed 1-hour bar only. |
| 15 minutes | Entry and execution timeframe | Latest completed 15-minute bar only. |
| 5 minutes | Short-term momentum confirmation | Latest completed 5-minute bar only. |

The earlier reference to a 1-minute timeframe is not part of v4.

## Williams Alligator definition

Use the same no-lookahead implementation as v3 on each timeframe:

| Line | Input | Period | Display offset |
| --- | --- | ---: | ---: |
| Jaw | Median price `(high + low) / 2` | 13-period SMMA | 8 bars |
| Teeth | Median price | 8-period SMMA | 5 bars |
| Lips | Median price | 5-period SMMA | 3 bars |

At a decision time, display offsets use only values computable from completed
past/current bars. They never use future prices.

### Bullish Alligator open

On a completed bar:

- Lips > Teeth > Jaw.
- All three lines are rising over the existing 3-bar slope lookback.
- Lips–Jaw separation is at least the existing 0.02% threshold.
- Separation is widening versus the prior slope-lookback point.

### Bearish Alligator open

The exact inverse:

- Lips < Teeth < Jaw.
- All three lines are falling over the 3-bar slope lookback.
- The same minimum separation threshold applies.
- Separation is widening in the bearish direction.

## Alignment and entry

### Long setup

Allow a long trade only when the latest completed 1h, 15m, and 5m bars all show
a bullish Alligator open, and the 15-minute Heikin-Ashi candle body is above its
Lips line.

### Short setup

Allow a short trade only when the latest completed 1h, 15m, and 5m bars all show
a bearish Alligator open, and the 15-minute Heikin-Ashi candle body is below its
Lips line.

### Trigger

Enter only when the 15-minute setup transitions from not fully aligned to fully
aligned. Do not re-enter on every subsequent aligned 15-minute bar.

The earliest simulated fill is the next 15-minute bar open. A real future
execution design must separately handle short-sale availability and broker
locate requirements.

## Stops, target, and risk controls

| Rule | Long | Short |
| --- | --- | --- |
| Initial stop | 0.05% below the completed 15-minute Jaw | 0.05% above the completed 15-minute Jaw |
| Target | 1R from entry | 1R from entry |
| Initial risk | 0.15% of current model equity | 0.15% of current model equity |
| RRMS tiers | 0.15%, 0.35%, 0.70%, 1.50% | Same |
| Quantity | Whole SPY shares, capped by planned loss including modeled costs | Same |

The 0.05% Jaw buffer is a versioned parameter, not an informal judgement. It
must be used consistently in every v4 test.

## Session and holding rules

Until separately changed, v4 inherits the v3 SPY session controls:

- Regular trading hours only.
- No new entry in the first regular-session hour.
- No new entry in the final regular-session hour.
- No new Friday entries.
- Weeknight holding allowed.
- Force-close any open trade before the weekend.
- One open position maximum for SPY.

## Macro relationship

V4 permits both long and short technical setups. The future Macro Dashboard
must eventually decide which directions are enabled:

| Macro stance | v4 permission |
| --- | --- |
| Bullish | Long setups only |
| Bearish | Short setups only |
| Neutral | No new trade |

Before that integration exists, v4 backtests must explicitly state whether they
are testing both directions without a macro filter or a manually fixed regime.

## Required implementation and validation

1. **Complete:** Extend the indicator engine to align completed 1h, 15m, and 5m bars.
2. **Complete:** Add no-lookahead multi-timeframe alignment and transition detection.
3. **Complete:** Add the 0.05% 15-minute-Jaw stop buffer to signal proposals.
4. Next: add long/short trade simulation and download/validate a reproducible multi-year SPY dataset for all three
   timeframes.
5. Then run fixed-risk and RRMS backtests, including transaction costs and a visual
   review of every entry.
6. Compare v4 with v3 without changing either locked version in place.

## Initial data-engine check — 2026-07-17

Read-only IBKR regular-session SPY data was saved for an initial alignment
check: 4,680 five-minute bars, 1,560 fifteen-minute bars, and 420 one-hour
bars across the latest 60 days. Validation found no duplicate timestamps or
invalid OHLC rows.

The completed-bar engine found 15 raw alignment transitions (13 long, 2 short).
This is only a data and signal-engine check; it is **not** a backtest result and
does not measure profitability, costs, drawdown, or execution quality.

## Initial 60-day backtest check — 2026-07-17

The same 60-day data was used to verify the long/short backtester with 1 bp
adverse slippage per side, $0.005/share commission per side, the 0.05% Jaw
buffer, a 1R target, and inherited v3 session/weekend rules.

| Measure | Fixed 0.15% risk | RRMS |
| --- | ---: | ---: |
| Raw / eligible signals | 15 / 8 | 15 / 8 |
| Completed trades | 5 | 5 |
| Long / short trades | 4 / 1 | 4 / 1 |
| Win rate | 40.0% | 40.0% |
| Net P&L on $100,000 | -$232.07 | +$210.18 |
| Profit factor | 0.49 | 1.32 |
| Average R | -0.307R | -0.307R |
| Maximum drawdown | $380.15 | $507.04 |

Five trades is far too small to support any conclusion. RRMS made dollar P&L
positive by increasing risk after losses; it did not improve the underlying
negative average R. The saved trade review is under
`outputs/strategy_01/v4/spy/initial_60d/trade_review.html`.

## Two-year preliminary backtest — 2026-07-17

The resumable local cache now contains 39,564 five-minute bars, 13,188
fifteen-minute bars, and 3,916 one-hour bars. It reaches at least 3 July 2024
for the lower timeframes. Re-running the downloader with the same target added
zero bars, proving that saved history is reused rather than downloaded again.

| Measure | Fixed 0.15% risk | RRMS |
| --- | ---: | ---: |
| Raw / eligible signals | 120 / 68 | 120 / 68 |
| Completed trades | 42 | 42 |
| Long / short trades | 34 / 8 | 34 / 8 |
| Wins / losses | 20 / 22 | 20 / 22 |
| Win rate | 47.6% | 47.6% |
| Net P&L on $100,000 | -$675.42 | +$1,810.97 |
| Profit factor | 0.78 | 1.27 |
| Average R | -0.106R | -0.106R |
| Maximum drawdown | $1,185.36 | $1,949.77 |

The fixed-risk result is negative, and average R is negative. RRMS creates a
positive dollar P&L by placing larger trades after losses; it does not repair
the underlying trade expectancy. Therefore V4 is not validated and must not
move to shadow, paper, or live trading. The fixed-trade visual review is saved
at `outputs/strategy_01/v4/spy/two_year_preliminary_2026-07-17/trade_review.html`.

## Non-goals

- No TradingView dependency for calculation or execution.
- No live or paper order placement.
- No indicator tuning after viewing individual outcomes; any change creates v5
  or a named v4 experiment.
