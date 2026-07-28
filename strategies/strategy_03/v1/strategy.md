# Strategy 03 v1 — Single-timeframe Alligator mouth opening

Status: historical research only. No order submission is enabled.

## Rules tested

1. Test each timeframe independently: 15 minutes and 1 hour.
2. Long when a completed bar transitions from a non-bullish state into an open bullish Alligator: Lips above Teeth above Jaw, all three rising, sufficiently separated, and widening.
3. Short when a completed bar transitions into the inverse bearish state.
4. Enter at the next immediate bar open; never fill on the signal bar.
5. Stop beyond the signal-bar Jaw by `max(minimum tick, 0.10 × ATR(14))`.
6. Take profit at 1:1 realised entry-to-stop risk.
7. No first-hour, final-hour, or Friday entries. Close open positions before the weekend.
8. No VIX, macro, support/resistance, Heikin-Ashi, or higher-timeframe confirmation filter.

## Risk profiles

The test records both fixed 0.15% account risk and the existing RRMS progression. Fixed sizing is the primary measure of whether the signal itself has an edge; RRMS cannot repair a negative-expectancy signal.
