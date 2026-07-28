# Strategy 04 Pine v0.3 status

## Implemented

- All v0.2 causal safeguards.
- Mandatory repeated-pivot base structure.
- Six-bar minimum pivot separation.
- Maximum merged width of 0.50 ATR.
- Two-step rejection confirmation.
- Three-bar confirmation window.
- Minimum directional body of 0.15 ATR.
- Five-bar rejection cooldown.
- One nearest zone per side in Clean mode.
- Broken zones and lifecycle markers hidden from Clean mode.
- Full event history retained in Audit mode.
- No trade entries, orders, or broker actions.

## Python reference result

- Dataset: SPY one-hour standard bars.
- Range: 2021-04-19 through 2026-07-16.
- Bars: 9,189.
- Qualified zones: 177.
- Demand: 77.
- Supply: 100.
- Rejection events: 252.
- Volume-confluence events: 71.
- Qualified with volume already present: 28.
- Frozen-geometry violations: 0.
- Availability/look-ahead violations: 0.
- Thirty review charts generated.

For comparison, v0.2 produced 485 qualified zones and 1,592 rejection events
on the same data.

## Pending

The project has no local Pine compiler. Paste
`ai_trade_confluence_reaction_zones_v0_3.pine` into TradingView on a SPY
one-hour standard-candlestick chart and confirm:

1. No compiler or runtime diagnostics.
2. Clean mode contains at most one demand and one supply zone.
3. Clean mode has no T/R/B/F/U marker clutter.
4. A zone does not qualify until the second separated pivot.
5. Audit-mode T and R markers follow the staged rejection sequence.

Do not publish this private validation build.
