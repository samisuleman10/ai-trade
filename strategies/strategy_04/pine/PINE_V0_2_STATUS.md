# Strategy 04 Pine v0.2 status

## Implemented

- Frozen zone geometry and score at qualification.
- Stable `Q` score plus separate current `C` score.
- Exact-bar `T`, `R`, `B`, `F`, and `U` lifecycle markers.
- Causal role-flip visual segments.
- Terminal box endpoints.
- Nearest-zone ranking in Clean mode.
- Full-history Audit mode.
- POC-only volume scoring; VAH and VAL are context only.
- POC must fall inside the zone to add confluence.
- No trade signals, orders, or broker actions.

## Automated validation

- Python Strategy 04 tests: 5 passed.
- SPY one-hour cached bars: 9,189.
- Cached range: 2021-04-19 through 2026-07-16.
- Qualified v0.2 zones: 485.
- Qualification scores: 285 at Q2 and 200 at Q3.
- Frozen-geometry violations: 0.
- Availability/look-ahead violations: 0.
- Thirty deterministic review charts generated.

## Pending TradingView validation

The project has no local Pine compiler. Paste
`ai_trade_confluence_reaction_zones_v0_2.pine` into TradingView on a SPY
one-hour standard-candlestick chart and confirm:

1. There are no compiler or runtime diagnostics.
2. Clean mode shows no more than the configured nearest zones per side.
3. `Q` scores and zone boundaries remain unchanged after qualification.
4. Event markers appear on the actual lifecycle bars.
5. A role flip starts a new opposite-colour segment at `F`.

Do not publish this private validation build.
