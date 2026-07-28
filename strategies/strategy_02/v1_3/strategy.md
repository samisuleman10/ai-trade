# Strategy 02 v1.3 — Higher-timeframe structure

This version corrects the timeframe and structure interpretation.

- **Structure and confirmation timeframe:** completed 1-hour bars.
- **Entry and execution timeframe:** completed 15-minute bars; fill reference is
  the next immediate 15-minute bar open.
- **Support/resistance:** causal ZigZag-style Heikin-Ashi structure using the
  course settings Depth `18`, Deviation `5`, Backstep `3`.
- A single 15-minute wick can never create support or resistance.
- A 1-hour swing becomes available only after its three-bar backstep
  confirmation has completed.
- Support dots are one tick below the confirmed 1-hour swing wick; resistance
  dots are one tick above it.
- A completed 1-hour wick breaking an active level invalidates that level.
- The stop is another `max(1 tick, 0.10 × 1-hour ATR(14))` beyond the dot.

## Scenario 2

For a long, the latest completed 1-hour Alligator remains open downward and a
valid 1-hour support exists. A completed 15-minute Heikin-Ashi candle crosses
and closes above its 15-minute Jaw; entry is referenced at the next 15-minute
bar open.

For a short, the latest completed 1-hour Alligator remains open upward and a
valid 1-hour resistance exists. A completed 15-minute Heikin-Ashi candle
crosses and closes below its 15-minute Jaw; entry is referenced at the next
15-minute bar open.

The mapping is causal: the 15-minute layer can only see 1-hour bars whose
closing time is at or before the 15-minute decision time.
