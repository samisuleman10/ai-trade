# Current Strategy 02 v1 interpretation

The canonical implementation is `src/ai_trade/strategy_02_v1.py`.

Strategy 02 uses the Cambist reference only for confirmed structural support
and resistance:

- Long stop: below the latest confirmed support.
- Short stop: above the latest confirmed resistance.
- RSI and RSI divergence are not calculated and are not entry filters.
- The support/resistance pivot becomes usable only after its right-side bars
  have closed, preventing lookahead in historical testing.

The earlier `strategy_02.py` experiment is superseded because it retained
unused RSI-divergence metadata. It must not be used for Strategy 02 v1 results.
