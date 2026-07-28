# Strategy 02 v3 — 4-hour trend, 1-hour reversal execution

Status: historical research only. No order submission is enabled.

## Rule set tested

1. The latest completed 4-hour Alligator must be open and directional: bullish for a long, bearish for a short.
2. On the 1-hour chart, the Alligator must be open in the opposite direction, representing a pullback against the 4-hour trend.
3. A completed Heikin-Ashi 1-hour body must cross the 1-hour Jaw in the trade direction. A wick alone is not sufficient.
4. Stop loss is beyond causal, confirmed 1-hour ZigZag support (long) or resistance (short), plus the existing ATR/tick buffer.
5. Entry is the next 1-hour bar open. Target is 1:1 realised risk/reward.
6. No entries in the first hour, final hour, or on Friday; Friday positions close at the configured Friday close.
7. The latest completed 15-minute VIX close must be strictly below 20.

## Important interpretation

This version seeks a 1-hour pullback reversal **in the direction of** a confirmed 4-hour trend. It is intentionally much more selective than v2.
