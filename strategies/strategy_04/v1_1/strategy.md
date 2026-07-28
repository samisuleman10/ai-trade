# Strategy 04 — Version 1.1

## Purpose

Test the strongest finding from the Version 1 losing-long audit without
altering the original baseline.

## Only change from Version 1

For a long trade, the 15-minute trigger candle's low may penetrate no more
than 25% of the active one-hour demand-zone width.

Formula:

`(zone upper boundary - trigger low) / zone width <= 0.25`

The boundary value of 0.25 is allowed. A deeper reaction is rejected and does
not consume the zone; a later valid shallow reaction may still qualify.

## Rules retained unchanged

- One-hour v0.3 zones provide location.
- Fifteen-minute candles provide entry confirmation.
- Shorts retain the complete Version 1 trigger logic.
- Entry is the next immediately following 15-minute open.
- Stop is outside the zone by 0.05 × latest completed one-hour ATR(14).
- Target is 1R.
- No entries during the first or final hour.
- No Friday entries and positions close before the weekend.
- Fixed risk is 0.15%.
- RRMS tiers are 0.15%, 0.35%, 0.70%, 1.5%, and 1.5%, resetting after a
  profit or the fifth consecutive negative exit.

## Research warning

The 25% threshold was discovered on the same SPY sample used for the Version 1
review. Version 1.1 is therefore an in-sample hypothesis and must not replace
Version 1 until it succeeds on unseen data.
