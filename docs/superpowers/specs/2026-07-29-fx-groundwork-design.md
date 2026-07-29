# FX Groundwork — EUR/USD and GBP/USD for Strategy 04

Date: 2026-07-29
Status: approved design, pending implementation plan

## Purpose

Make spot FX a first-class research instrument so Strategy 04 v1.1 can run on
EUR/USD (instrument 5) and GBP/USD (instrument 6) and publish to the dashboard.
Strategy 04 v1.2 (the two rejection filters, see
`strategies/strategy_04/v1_2/strategy.md`) is deferred until this foundation
lands; its ablation will then run on SPY, QQQ, DIA, EURUSD, and GBPUSD.

MGC is explicitly out of scope. Its cached 15-minute history covers only 90
days (IBKR `CONTFUT` requests reject an end time, so no backfill is possible),
which is insufficient for Strategy 04's multi-year 15-minute entry stream.

## Why FX needs groundwork at all

Three verified blockers, each addressed by one section below:

1. **No FX fetch path.** `fetch_historical_bars()` hardcodes
   `whatToShow="TRADES"`; IBKR does not serve TRADES for `CASH` contracts.
   FX needs `MIDPOINT` on `IDEALPRO`.
2. **FX has no volume, and the zone indicator silently breaks without it.**
   `_session_profile()` weights price bins by `max(row.volume, 0.0)`. With
   all-zero volume the profile is flat and `max()` returns the first bin:
   POC is systematically reported at the session low, and VAH/VAL walk from
   there. Zones would then qualify (`minimum_confluence_score = 2`) partly on
   a deterministic wrong answer — results would look normal and be
   uninterpretable.
3. **FX trades 24/5.** The equity session rules (no entry before 10:30, none
   from 15:00 New York) and the calendar-day session grouping used by the
   profile do not describe an FX day.

## Decisions (made 2026-07-29)

| Question | Decision |
| --- | --- |
| Ordering | FX groundwork first; Strategy 04 v1.2 afterwards |
| Volume substitute | TPO time-at-price profile mode, A/B measured on equities |
| Session model | 24/5 day, 17:00→17:00 ET boundary, rollover hour blocked |
| Cost model | Commission in bps of notional + per-order minimum; spread as fixed half-spread in slippage |
| Done means | Foundation + v1.1 baseline runs on both pairs + TPO-vs-volume A/B report |
| MGC | Dropped from scope entirely |

## 1. Data layer

- `fx_contract(base: str, quote: str) -> Contract` in
  `src/ai_trade/market_data.py`: `secType="CASH"`, `exchange="IDEALPRO"`,
  `symbol=base`, `currency=quote`. Research-only, like the other contract
  helpers.
- `fetch_historical_bars()` gains `what_to_show: str = "TRADES"`. Existing
  callers are unchanged; FX passes `MIDPOINT` with `use_rth=False`. The epoch
  timestamp parsing in `historicalData` already applies to MIDPOINT bars.
- New `src/ai_trade/download_fx_history.py`:
  - Chunked backfill using `end_date_time` paging (allowed for `CASH`,
    unlike `CONTFUT`), respecting IBKR pacing limits between requests.
  - Targets: 5 years of 15m and 1h for EURUSD and GBPUSD →
    `data/market_data/ibkr/EURUSD/v1_5y/` and
    `data/market_data/ibkr/GBPUSD/v1_5y/` via the existing `save_bars()`.
  - IBKR reports `volume = -1` on MIDPOINT bars; the downloader normalizes
    volume to `0.0` and the validation report records
    `"volume": "none (midpoint data)"` so no downstream reader can mistake
    it for real volume.
  - Dedupe/stitch across chunks with strict timestamp ordering; the
    existing `validate_bars()` report gates acceptance.

## 2. TPO profile mode in the indicator

- `Strategy04IndicatorParameters` gains
  `profile_weighting: Literal["volume", "time"] = "volume"`. Every existing
  preset keeps the default; no committed result changes.
- In `"time"` mode, `_session_profile()` allocates a weight of 1.0 per bar,
  split evenly across that bar's occupied bins (time-at-price), exactly as
  the volume mode splits `row.volume`. POC/VAH/VAL derivation is otherwise
  identical.
- Session grouping becomes instrument-aware: a `session_date` function
  chooses between the current New York calendar date (equities) and the
  17:00-ET-boundary FX day (a bar at 21:00 UTC Sunday belongs to Monday's
  session). Implemented as
  `session_day_boundary: Literal["calendar", "fx_17et"] = "calendar"` on
  `Strategy04IndicatorParameters`, so current behaviour is the default.
- **A/B bridge report** — `src/ai_trade/compare_profile_weighting.py`:
  runs the v0.3 indicator on SPY, QQQ, and DIA under both weightings and
  reports, per symbol: qualified-zone overlap (count and identity),
  qualification-score deltas, and the diff in v1.1 candidate signals.
  Output: `strategies/strategy_04/analysis/tpo_vs_volume/REPORT.md` + JSON.
  This report is the bridge that says how much equity-validated behaviour
  transfers to volume-less instruments.

## 3. FX session and cost preset

- New FX `BacktestConfig` preset (module-level factory, mirroring `_config()`
  usage):
  - `session_timezone="America/New_York"` retained.
  - Entry window: entries blocked 17:00–18:00 ET (daily rollover: thin
    books, wide spreads, IBKR maintenance). Expressed with the existing
    `entry_window_start`/`entry_window_end` midnight-spanning support.
  - `block_friday_entries=True`; flat before the weekend with
    `friday_close_time=(16, 45)` (market closes Friday 17:00 ET).
  - Sunday-open entries are allowed after 18:00 ET Sunday (first tradable
    bars of the FX week); the rollover block covers the open hour itself.
- Cost model additions to `BacktestConfig`:
  - `commission_bps_per_side: float | None = None` — when set, commission
    per side = `max(notional × bps / 10_000, min_commission_per_order)`
    where notional = fill price × quantity. Takes precedence over the
    per-share/per-contract fields; the existing
    `costs = quantity * commission * 2` expression gains this third branch.
  - `min_commission_per_order: float = 0.0`.
  - FX preset values: 0.20 bps per side, $2.00 minimum (IBKR IDEALPRO
    tier 1), and a conservative fixed half-spread folded into
    `slippage_bps_per_side` (EURUSD 0.5 bps, GBPUSD 0.7 bps per side).
    These are parameters, not constants; the existing cost-stress workflow
    covers sensitivity.
- Position sizing: quantity = integer currency units (multiplier 1). At
  0.15% risk on $100k with a typical stop this is roughly 50k–100k units;
  unit tests exercise the commission minimum and bps math at that scale.

## 4. Baseline runs and dashboard

- Run Strategy 04 **v1.1** (current research candidate) on both pairs with
  the FX preset and TPO indicator mode →
  `strategies/strategy_04/v1_1/results/eurusd_1h_15m/` and
  `.../gbpusd_1h_15m/`, writing the standard contract file set
  (`candidate_signals.csv`, `fixed_trades.csv`, `fixed_summary.json`,
  `rrms_*`, `backtest_report.json`) and ending with
  `publish_result_directory()`. The runs appear in the dashboard with zero
  dashboard code changes, ledger audit included.
- Each `backtest_report.json` carries an explicit warning: TPO-qualified
  zones, midpoint prices, modelled spread — research only; read the
  TPO-vs-volume bridge report before comparing against equity results.
- RRMS output is produced by the shared harness, but per the existing RRMS
  policy no RRMS conclusion is drawn until a fixed-risk edge is accepted.

## 5. Testing (TDD throughout)

- Contract and fetch: `fx_contract()` fields; `what_to_show` passthrough
  (mocked client); TRADES default preserved.
- Downloader: chunk paging, dedupe/ordering, volume normalization to 0,
  validation-report contents.
- Profile: known-bars fixtures where time and volume weighting disagree;
  all-zero-volume input produces a correct TPO profile in `"time"` mode and
  is the motivating regression case.
- Session date: UTC bars around the 17:00 ET boundary (including DST
  transitions) map to the correct FX session day; equities unaffected.
- Session rules: rollover-hour block, Sunday-open allowance, Friday close.
- Costs: bps commission, per-order minimum binding and non-binding, third
  branch precedence over per-share/per-contract.
- End-to-end: small FX fixture through signals → backtest → result files →
  publishable bundle.

## 6. Out of scope

- Strategy 04 v1.2 filters (next project; spec unchanged).
- MGC in any form (15m backfill would require concrete-expiry roll logic).
- Historical BID_ASK spread data (candidate follow-up if fixed-spread
  assumptions need validating).
- Any RRMS evaluation, paper, or live FX execution.

## Sequencing after this lands

Strategy 04 v1.2 ablation (base/a/b/ab, per its spec) runs on SPY, QQQ, DIA,
EURUSD, and GBPUSD — five instruments, each judged on its own evidence per
the v1.1 precedent.
