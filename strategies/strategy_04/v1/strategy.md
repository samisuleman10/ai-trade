---
strategy_id: strategy_04
version: 1.0
status: historical_backtest
created: 2026-07-28
---

# Strategy 04 v1 — 1h zones with 15m reaction entries

## Purpose

The one-hour Confluence Reaction Zones indicator determines **where** a trade
may be considered. A completed 15-minute reaction candle determines **when** a
historical entry becomes eligible.

This version is research-only. It generates no live broker orders.

## Causal timeframe alignment

1. Strategy 04 indicator v0.3 builds zones from completed one-hour bars.
2. A zone must already be qualified before a 15-minute trigger candle opens.
3. A zone qualifying when a 15-minute candle closes cannot use that same
   candle as confirmation.
4. The reaction is evaluated only after the 15-minute candle closes.
5. The earliest simulated fill is the next immediately following 15-minute
   bar's open.

## Long setup

1. A qualified one-hour demand zone is active, touched, rejected, or verified.
2. The previous completed 15-minute candle closed above the zone.
3. The trigger candle intersects the zone.
4. The trigger candle is bullish.
5. The trigger candle closes back above the zone's upper boundary.
6. Entry is simulated at the next 15-minute bar open.

## Short setup

1. A qualified one-hour supply zone is active, touched, rejected, or verified.
2. The previous completed 15-minute candle closed below the zone.
3. The trigger candle intersects the zone.
4. The trigger candle is bearish.
5. The trigger candle closes back below the zone's lower boundary.
6. Entry is simulated at the next 15-minute bar open.

## Stop, target, and collisions

- Long stop: one-hour zone lower boundary minus 0.05 × latest completed
  one-hour ATR(14).
- Short stop: one-hour zone upper boundary plus 0.05 × latest completed
  one-hour ATR(14).
- Target: 1.0R from the actual simulated entry price.
- If stop and target are both touched inside one bar, the stop is assumed to
  occur first.
- A gap that places the next-bar entry on the wrong side of the structural stop
  invalidates that entry.

## Zone reuse and overlapping zones

- At most one signal is permitted per zone identifier.
- If one 15-minute reaction touches multiple overlapping qualified zones, the
  highest current confluence score is selected.
- Ties prefer the highest qualification score, then the narrowest zone, then
  the oldest zone identifier.
- All overlapping zones participating in the same selected reaction are marked
  consumed so one price response is not counted repeatedly.

## Session rules

- Instrument: SPY for the first validation.
- Session: US regular trading hours.
- No new entries before 10:30 America/New_York.
- No new entries from 15:00 America/New_York.
- No Friday entries.
- Existing positions may remain open overnight from Monday through Thursday.
- Any position still open is closed in the final Friday bar ending at 16:00
  America/New_York.
- Only one position may be open at a time.

## Sizing and costs

Two reports use the same price signals:

1. Fixed sizing risks 0.15% of current equity per trade.
2. Five-loss RRMS uses 0.15%, 0.35%, 0.70%, 1.50%, and 1.50%. Every negative
   exit counts as a loss, including a negative weekend close. A profitable exit
   resets the sequence, and the sequence resets after the fifth consecutive
   loss.

The initial research account is $100,000. The simulation applies one basis
point of adverse slippage per side and $0.005 commission per share per side.

## Validation outputs

Every SPY run must save:

- Candidate signal ledger.
- Fixed-risk trade ledger and statistics.
- Five-loss RRMS trade ledger and statistics.
- Backtest configuration and data ranges.
- At least ten deterministic charts showing the one-hour zone, 15-minute
  trigger, entry, stop, target, and exit.

The result remains preliminary until the saved trades are reviewed visually
and robustness tests are completed.

