---
strategy_id: strategy_04
component: one_hour_indicator
version: 0.1
status: private_prototype
created: 2026-07-28
---

# Strategy 04 one-hour indicator specification v0.1

## Scope

This version creates and evaluates one-hour zones only. It deliberately has:

- No 15-minute logic.
- No buy/sell arrows.
- No position sizing.
- No backtest trades.
- No broker connectivity or order authority.

## Data

- Initial instrument: SPY.
- Timeframe: one hour.
- Primary historical source: cached IBKR OHLCV.
- Cached range used for the initial review: 2021-04-19 through 2026-07-16.
- Volume-at-price is approximated from hourly bar ranges and volume. It is not
  tick-level exchange volume.

## Locked v0.1 defaults

| Parameter | Value |
| --- | ---: |
| ATR period | 14 |
| Pivot left bars | 5 |
| Pivot right confirmation bars | 3 |
| Pivot minimum width | 0.12 ATR |
| Pivot maximum width | 0.55 ATR |
| Structure lookback | 10 bars |
| Order-block search | 6 bars |
| Displacement threshold | 1.20 ATR |
| Merge distance | 0.25 ATR |
| Maximum merged width | 1.00 ATR |
| Volume-profile rows | 24 |
| Value area | 70% |
| Volume-reference distance | 0.30 ATR |
| Volume-reference life | 40 bars |
| Minimum confluence score | 2 |
| Zone invalidation buffer | 0.05 ATR |
| Maximum zone age | 240 bars |
| Broken-zone retest window | 40 bars |
| Maximum simultaneous live zones | 20 |

## Pivot support/resistance

A pivot low becomes a demand candidate only after the three required bars to
its right have completed. A pivot high becomes a supply candidate under the
inverse condition.

The zone begins with the pivot rejection wick. A minimum ATR width is applied
when the wick is too small, and a maximum ATR width prevents unusually large
candles from creating unusably wide zones.

The drawing may visually originate at the pivot candle, but the candidate's
`available_timestamp` is the close of the confirmation bar.

## Order blocks

### Bullish

1. A completed bar closes above the highest high of the previous ten bars.
2. The bar is bullish.
3. Its body is at least 1.20 ATR.
4. The last bearish candle within the previous six bars becomes a demand
   candidate.

### Bearish

The inverse rules create a supply candidate from the final bullish candle.

The candidate is unavailable until the structure-breaking displacement bar has
closed.

## Session volume references

For each completed New York session:

1. Find the session high and low.
2. Divide the range into 24 equal price rows.
3. Distribute each hourly bar's volume equally across the rows overlapped by
   its high-low range.
4. The row with the greatest allocated volume becomes POC.
5. Expand from POC toward the higher-volume adjacent row until 70% of session
   volume is included.
6. The resulting outer row centers are VAH and VAL.

POC, VAH and VAL become available only after the session is complete. They do
not independently create zones; they add one volume-confluence point to a
nearby pivot or order-block zone.

## Merging and score

Same-side candidates merge when:

- Their ranges overlap or are no more than 0.25 ATR apart.
- Their combined range is no wider than 1.00 ATR.

One point is awarded for each independent evidence type:

- Pivot.
- Repeated pivot.
- Order block.
- Session volume profile.
- Verified role flip.

A candidate becomes a displayed qualified zone at score two. Its
`qualified_timestamp` is the moment the second independent confirmation
becomes available, never the original pivot time.

## Lifecycle

```text
candidate → active → touched → rejected
                         └────→ broken → role-flip retest → verified
candidate/active/verified → expired
```

- Touch: bar range intersects a zone after it was available.
- Rejection from demand: the bar touches the zone and closes above its upper
  boundary.
- Rejection from supply: inverse.
- Demand break: completed close below the lower boundary by more than 0.05 ATR.
- Supply break: inverse.
- Role-flip retest: a broken demand zone is approached from below and closes
  below it as supply, or a broken supply zone is approached from above and
  closes above it as demand.
- Broken zones expire after 40 bars without a verified retest.
- Other zones expire after 240 bars.

## No-look-ahead requirements

1. Only completed bars update the indicator.
2. Pivots cannot qualify before their right-side confirmation bars complete.
3. Order blocks cannot qualify before the displacement/structure-break bar
   closes.
4. Session references cannot be used before the session completes.
5. The origin time and availability time are stored separately.
6. Historical research uses the availability/qualification time, not the
   earlier visual origin.

## First visual-review questions

1. Are 0.25 ATR merges too permissive?
2. Does one volume reference make too many candidates qualify?
3. Are wick-based zones too narrow or too wide?
4. Do order blocks overlap the pivot zones in meaningful locations?
5. Are role-flip retests being labeled where a trader would visually expect?
6. Should only POC add score, with VAH/VAL displayed as context?

No parameter should be optimized for profit during this indicator-only phase.
