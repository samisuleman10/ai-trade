# Strategy 02 v1.1 - Wick-safe structure dots

This version refines only the structural level and stop placement.

- A support cluster uses the final occurrence of the lowest equal wick.
- The support dots are one instrument tick below that wick.
- A resistance cluster uses the final occurrence of the highest equal wick.
- The resistance dots are one instrument tick above that wick.
- The stop is then placed a second buffer beyond the dots:
  `max(1 tick, 0.10 x ATR(14))`.
- RSI and RSI divergence are not used.

This prevents the structural dots from crossing the wick that created them and
keeps the protective stop visibly outside the dots.
