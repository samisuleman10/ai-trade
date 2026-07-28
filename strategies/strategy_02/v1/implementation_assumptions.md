# Strategy 02 v1 - Independent Cambist Implementation

## Status

Prototype indicator and signal generator. No backtest conclusion, shadow mode,
paper order, or live order is authorized.

The available `Cambistfile.ex4` is compiled MT4 code. This implementation is
based on the course rules and screenshots and does not claim exact parity.

## Implemented interpretation

- Long reversal: Alligator remains open/down, then completed Heikin-Ashi close
  crosses above the Jaw. Stop is below the latest confirmed support.
- Short reversal: Alligator remains open/up, then completed Heikin-Ashi close
  crosses below the Jaw. Stop is above the latest confirmed resistance.
- Fill assumption: next immediate bar open, never the decision-bar close.
- Initial target: 1R, matching equal risk and reward in the course notes.
- Stop buffer: `max(instrument tick, 0.10 x ATR(14))` beyond structure.

## Cambist-style structure assumptions

- Heikin-Ashi OHLC is calculated locally.
- Wilder RSI(18) is calculated on Heikin-Ashi close.
- A structural pivot uses 5 completed bars on the left and 3 on the right.
- A pivot is not usable until all 3 right-side bars have closed. The code
  records both the historical pivot time and its later confirmation time.
- Bullish divergence means a lower price-pivot low with a higher RSI value.
- Bearish divergence means a higher price-pivot high with a lower RSI value.
- Divergence is recorded but is not mandatory by default. A strict mode can
  require it so both interpretations can be compared without rewriting code.

## Still to decide before a formal backtest

- First instrument and test period.
- Whether entry uses Heikin-Ashi close or normal close.
- Whether RSI divergence is mandatory for each trade.
- Whether the Strategy 01 macro, session, overnight, Friday/weekend, RRMS, and
  higher-timeframe rules also apply to Strategy 02.
- Visual comparison against the `.ex4` output to tune pivot and RSI parameters.
