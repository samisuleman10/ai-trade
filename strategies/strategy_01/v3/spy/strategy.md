---
id: strategy_01_v3_bill_williams_alligator_rrms
name: Bill Williams Alligator + Heikin Ashi + RRMS — v3
version: 0.3.0
status: locked_preliminary_backtest
execution_mode: historical_backtest_only
primary_venue: IBKR
primary_instrument: SPY
market: S&P 500 ETF
direction: long_only_manual_bullish_regime
trend_timeframe: 4h
entry_timeframe: 1h
position_sizing: rrms
owner: Sami
last_updated: 2026-07-16
---

# Strategy 01 v3: Bill Williams Alligator + Heikin Ashi + RRMS

> **Locked baseline — 2026-07-16.** This is the current Strategy 01 research
> configuration. Its two-year Friday-close run is preserved under
> `docs/strategy_01/v3/spy/locked_baseline_2026-07-16/`. Do not alter its rules,
> data, or result interpretation in place; create a new version for any
> experiment. It remains historical-only and cannot submit paper or live orders.

## Purpose

An intraday trend-following strategy for the S&P 500. The 4-hour chart confirms
trend direction; the 1-hour chart supplies the entry. The Alligator filters
flat/ranging markets, Heikin Ashi reduces entry noise, and RRMS converts the
approved trade risk into a position size.

This strategy starts with historical backtesting only. It does not authorize
paper or live order submission.

## v3 change set

This is a separate hypothesis from the preserved v1 and v2 tests. Until the Macro
Dashboard supplies a regime value, its macro stance is set manually to
`bullish`, so v3 evaluates **long signals only**.

| Rule | v3 decision |
| --- | --- |
| Direction | Long only while the manual macro regime is bullish. |
| Timeframes | Completed 4-hour Alligator confirms direction; the completed 1-hour chart creates entries. |
| First hour | No new entry before 10:30 New York time. |
| Final hour | No new entry from 15:00 New York time. The last permitted 1-hour entry is 14:30. |
| Friday | No new entry at any time on Friday. |
| Overnight | Positions may remain open on weeknights. |
| Weekend | Force-close any remaining position in the Friday 15:45–16:00 New York bar. |

The future Macro Dashboard integration will replace the manual regime value
with `bullish`, `neutral`, or `bearish`. A neutral regime takes no trade; a
bearish regime will require a separately tested short-enabled version.

## System role

```text
Macro stance -> trade allowed? -> strategy signal -> RRMS size -> risk gateway
-> execution adapter -> broker reconciliation -> trade review
```

Macro is a filter, not an entry trigger. If the macro stance does not permit
S&P 500 trading, the strategy creates no new entry signal.

## Instrument and data

| Item | Rule |
| --- | --- |
| Research / execution instrument | SPY through IBKR; use SPY bars for backtests and paper execution. |
| Continuous futures chart | May be used for visual research only; never submit an order against a continuous chart symbol. |
| Trend timeframe | The most recently completed 4-hour regular-session Alligator state is the background direction filter. At 10:30 and 11:30, it is normally the prior session's completed state; after 12:00, it can update from the completed 09:30–12:00 segment. The shorter opening segment is treated as complete at its actual 12:00 boundary; the afternoon segment completes at 16:00. |
| Entry timeframe | Completed 1-hour regular-session bars. |
| Data price | Real OHLCV bars timestamped and stored in UTC. Heikin Ashi is derived from those bars and is not an execution price. |
| Session | Regular trading hours only for entries and signals. Positions may remain open overnight on trading days. No new entry from 15:00 New York time or at any time on Friday. |
| Opening-hour rule | No new entries during the first regular-session hour. |
| Weekend rule | No position may be carried into a weekend. Any open position is force-closed in the Friday 15:45–16:00 New York bar. |

## Indicators

### Heikin Ashi

Derived per timeframe from real OHLC bars:

```text
HA close = (open + high + low + close) / 4
HA open  = (previous HA open + previous HA close) / 2
HA high  = max(high, HA open, HA close)
HA low   = min(low, HA open, HA close)
```

### Bill Williams Alligator

Use median price `(high + low) / 2` as input to smoothed moving averages.

| Line | Period | Display offset |
| --- | ---: | ---: |
| Jaw | 13 | 8 bars forward |
| Teeth | 8 | 5 bars forward |
| Lips | 5 | 3 bars forward |

The display offset must never introduce lookahead bias. At a decision time,
only values computable from completed bars at that time may be used.

## Definitions requiring numerical parameters

The original visual rules use the phrases "mouth open" and "parallel." Code
cannot use those phrases directly. Before the first backtest, this file must be
updated with numbers for:

```yaml
 alligator_parameters:
  slope_lookback_bars: TBD
  minimum_line_separation_percent: TBD
  separation_must_be_widening: TBD
  jaw_stop_buffer_percent: TBD
  maximum_stop_distance_percent: TBD
```

The first diagnostic uses exploratory values of a 3-bar slope lookback and
0.02% minimum Lips-to-Jaw separation. They are not final strategy parameters
and must be evaluated before the backtest version is frozen.

Provisional interpretation:

```text
Bullish open mouth: Lips > Teeth > Jaw, all three slope upward, and the
separation between lines is not compressed.

Bearish open mouth: Lips < Teeth < Jaw, all three slope downward, and the
separation between lines is not compressed.
```

## Entry rules

### Long

All conditions must be true:

1. Macro stance permits S&P 500 long entries.
2. On the completed 4-hour bar, the Alligator is bullish and open:
   `Lips > Teeth > Jaw`, all three lines rise, and the numerical
   open-mouth threshold is met.
3. On the completed 1-hour bar, the Alligator is bullish and open under the
   same definition.
4. The completed 1-hour Heikin Ashi candle body closes above the Lips.
5. No kill switch, trading-halt, or risk limit is active.

**Entry:** submit the planned order at the next 1-hour bar open. The
backtest must model this as next-bar execution, not same-bar execution. The
1-hour entry signal must agree with an already completed 4-hour confirmation
bar. The next executable 1-hour entry must be before 15:00 New York time and
may not be on Friday.

### Short

**Not active in v3.** Short signals are deliberately ignored while the manual
macro regime is bullish. This rule remains here only as the future bearish
regime candidate and must be tested separately before activation.

All conditions must be true:

1. Macro stance permits S&P 500 short entries.
2. On the completed 4-hour bar, the Alligator is bearish and open:
   `Lips < Teeth < Jaw`, all three lines fall, and the numerical
   open-mouth threshold is met.
3. On the completed 1-hour bar, the Alligator is bearish and open under the
   same definition.
4. The completed 1-hour Heikin Ashi candle body closes below the Lips.
5. No kill switch, trading-halt, or risk limit is active.

**Entry:** submit the planned order at the next 1-hour bar open.

The same opening-hour rule applies to short entries.

## Stop, target, and exits

| Item | Long | Short |
| --- | --- | --- |
| Initial stop | 1-hour Jaw minus configured buffer | 1-hour Jaw plus configured buffer |
| Initial target | Entry + 1R | Entry - 1R |
| R | `absolute value(entry - initial stop)` | `absolute value(entry - initial stop)` |
| Trend exit | **Test separately:** confirmed opposite setup or a defined mouth-closing rule | **Test separately:** confirmed opposite setup or a defined mouth-closing rule |

The Jaw chooses the stop from market structure. A maximum-stop-distance filter
may reject a setup whose stop is too wide; it must not move the stop inside the
Jaw merely to force a trade.

An open position may remain open overnight from one trading day to the next.
It may not remain open through a weekend: the backtest and later execution
logic must force-close any remaining position before the Friday regular session
ends.

## RRMS position sizing

RRMS is a sizing overlay. It does not decide entry direction, change the Jaw
stop, or prove that this strategy has an edge.

| RRMS state | Prior consecutive stop-losses | Risk of current account equity | On another stop-loss |
| --- | ---: | ---: | --- |
| Normal | 0 | 0.15% | Recovery 1 |
| Recovery 1 | 1 | 0.35% | Recovery 2 |
| Recovery 2 | 2 | 0.70% | Recovery 3 |
| Recovery 3 | 3 | 1.50% | Block new entries and require review |

```text
risk_dollars = current_account_equity * rrms_risk_percent
risk_per_unit = absolute_value(planned_entry_price - initial_stop_price)
quantity_by_risk = floor(risk_dollars / risk_per_unit)
final_quantity = min(quantity_by_risk, quantity_allowed_by_buying_power)
```

Rules:

- A profitable closed trade resets RRMS to `Normal`.
- A stop-loss event advances RRMS one tier.
- A break-even or other non-stop exit retains the current tier and is flagged
  for review.
- Four consecutive stop-losses block new Strategy 01 entries until a manual
  review clears the strategy.
- If final quantity is below the venue's minimum tradable size, reject the
  signal rather than exceed the risk budget.

## Required risk controls

- One open Strategy 01 position at a time during the initial release.
- No new order without a durable client order ID.
- Risk gateway validates symbol, side, quantity, account tier, buying power,
  existing exposure, daily loss stop, and trading session.
- Broker/exchange is the source of truth for order state, fills, positions, and
  balances.
- Every entry, exit, rejection, and RRMS state change is written to an audit
  log.

## Backtest requirements

The initial report must show the strategy with **both** sizing approaches:

1. Fixed 0.15% account risk on every trade.
2. RRMS tiered sizing.

For each approach, record:

- Trade count, win rate, profit factor, average R, drawdown, and equity curve.
- Long and short results separately.
- Entry-to-stop distance as a percentage of entry.
- RRMS tier used for every trade and maximum loss streak.
- Assumed fees, spread, slippage, and next-bar fill logic.
- In-sample and untouched out-of-sample performance.

## Promotion criteria

```text
specified -> parameterized -> backtest -> shadow -> paper -> limited_live
```

The strategy cannot progress until its open parameters are specified and it
passes the documented acceptance criteria for the current mode. A positive
backtest is not permission for live trading.

## v1 baseline reference

The preserved v1 run used 1,535 regular-session 15-minute bars and 2,540
1-hour bars downloaded from IBKR. It used the exploratory Alligator parameters,
1 basis point adverse slippage per side, USD 0.005 commission per share per
side, 1R targets, weekday overnight holding, and force-close before the
weekend.

| Sizing | Trades | Win rate | Profit factor | Net P&L on USD 100,000 model equity | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed 0.15% risk | 20 | 40.0% | 0.66 | -517.61 | 556.65 |
| RRMS | 20 | 40.0% | 1.23 | +619.01 | 1,218.54 |

The underlying v1 trade outcomes averaged **-0.175R**. RRMS increased the
apparent P&L by increasing risk after losses, but also increased drawdown
materially. It does not demonstrate that the entry strategy has an edge.
Strategy 01 v3 must be compared against the preserved v1 baseline before any
paper-trading decision.

## Preliminary v3 backtest result — 2026-07-16

The expanded test used matching 1-hour entry and 4-hour confirmation bars from
17 Jul 2024 through 16 Jul 2026. It retained
the manual bullish long-only filter, no final-hour entries, and no Friday
entries. There were 43 raw candidates, of which 19 passed v3's directional and
time filters; 17 became fixed-risk trades after the one-open-position rule was
applied.

| Sizing | Trades | Win rate | Profit factor | Net P&L on USD 100,000 model equity | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed 0.15% risk | 17 | 70.6% | 1.69 | +437.54 | 303.69 |
| RRMS | 17 | 70.6% | 1.85 | +710.67 | 503.34 |

V3 is better than the earlier v1/v2 results, but 17 trades is still far too
small a sample to validate an edge. Nine exits were Friday forced closes rather
than 1R targets or stop-losses, so their trade paths need particular review.
Do not paper trade this version yet; the next work is to inspect all 17 entries
and run an untouched out-of-sample period before changing strategy rules again.

## Open items before coding

1. Numerical definition of open mouth, parallel slope, and line separation.
2. Jaw buffer and maximum permitted stop distance.
3. Exact Friday force-close time and whether new Friday entries are permitted.
4. Whether a 1R target, mouth-closing exit, or a combination performs best.
5. Macro stance source and exact rule for allowing long and short entries.
