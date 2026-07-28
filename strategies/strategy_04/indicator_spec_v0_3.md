---
strategy_id: strategy_04
component: one_hour_indicator
version: 0.3
status: private_validation
created: 2026-07-28
---

# Strategy 04 one-hour indicator specification v0.3

## Purpose

Version 0.3 keeps the causal guarantees introduced in v0.2 and corrects the
over-selection visible in its first TradingView review. It remains an
indicator-only research build with no 15-minute entries or orders.

## Qualification rule

A zone cannot qualify from a single pivot combined with an order block or
volume reference.

It must first contain:

1. A confirmed pivot.
2. A second merged pivot reaction at least six one-hour bars later.

Order blocks and prior-session POC may increase the score, but they cannot
replace the repeated-pivot requirement.

## Locked v0.3 changes

| Parameter | v0.2 | v0.3 |
| --- | ---: | ---: |
| Repeated pivot required | No | Yes |
| Minimum pivot separation | None | 6 bars |
| Maximum merged width | 1.00 ATR | 0.50 ATR |
| Rejection confirmation | Immediate | Staged |
| Confirmation window | None | 3 bars |
| Minimum directional body | None | 0.15 ATR |
| Cooldown after rejection | None | 5 bars |
| Clean zones per side | 2 | 1 |
| Clean lifecycle markers | On | Off |
| Broken zones in Clean mode | Shown | Hidden |

Other causal and volume rules remain inherited from v0.2:

- Frozen qualified geometry and score.
- Later evidence is timestamped.
- Only prior-session POC can score.
- POC must lie inside the zone.
- VAH and VAL are optional context only.

## Staged rejection

For demand:

1. Price must first be completely above the zone, making the zone ready for a
   valid approach.
2. A later bar touches the demand zone.
3. Within the next three completed bars, a bullish candle must close above the
   upper boundary.
4. Its body must be at least 0.15 ATR.
5. After confirmation, that zone cannot generate another rejection for five
   bars.

Supply uses the inverse rules.

The touching candle cannot confirm its own rejection.

## Clean mode

Clean mode shows at most:

- One nearest demand zone below or containing current price.
- One nearest supply zone above or containing current price.

It hides broken zones, historical lifecycle markers, archived role-flip
segments, POC/VAH/VAL lines, and other qualified zones. Audit mode retains
those research details.

## Validation gate

Before adding 15-minute entries:

1. Pine v0.3 must compile on SPY one-hour standard candles.
2. Thirty v0.3 examples must be visually reviewed.
3. At least twenty Pine/Python zones must be reconciled.
4. The repeated-pivot, touch, confirmation, and cooldown timestamps must agree.
5. The one-hour rules must then be frozen.
