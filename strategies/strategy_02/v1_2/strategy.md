# Strategy 02 v1.2 - Wick-safe active structure

This version locks the visual rule clarified during historical review:

- Support dots sit one tick below their confirmed pivot wick.
- Resistance dots sit one tick above their confirmed pivot wick.
- If a later completed wick crosses an active level, those old dots disappear
  immediately.
- No new dots appear until another structural pivot is confirmed.
- Long stops sit an additional `max(1 tick, 0.10 x ATR(14))` below support.
- Short stops sit the same additional buffer above resistance.
- RSI and RSI divergence are not used.

Therefore displayed support/resistance dots never cross a completed wick, and
the protective stop remains farther outside the dots.
