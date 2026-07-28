# Strategy 04 Trade Audit View — Design

Date: 2026-07-28
Status: approved design, not yet implemented

## 1. Purpose

Give full visibility into why each Strategy 04 trade existed and what happened
to it, so that a trade can be confirmed correct against the written strategy
rules rather than assumed correct because a backtest produced it.

The primary question this view answers is:

> Was this trade correct?

Not "was this trade profitable". A losing trade that followed every rule is
correct. A winning trade that used an ATR value from after its own trigger bar
is a bug.

This view has no execution authority. It reads historical research artifacts
only.

## 2. Scope

In scope:

- Strategy 04 only, versions v1 and v1.1, symbols SPY, QQQ, and DIA.
- Every trade in the selected result is listed. No truncation, no sampling.
- Automated per-trade rule checks with a pass/fail result.
- A linked two-chart drill-down for a selected trade.

Out of scope for this design:

- Strategies 01, 02, and 03.
- Shadow-mode and live data.
- Recomputing indicators, zones, or trade outcomes anywhere outside the
  strategy producer.

## 3. Relationship to the existing visualization contract

`docs/design/strategy_visualization/shared/architecture_and_data_contract.md`
already defines a contract-first pipeline whose primary rule is:

> Strategy result generation must publish a validated, visualization-ready
> bundle. The dashboard must not reverse-engineer strategy-specific CSV and
> JSON files or recalculate trading indicators.

That contract is designed but unimplemented. `src/ai_trade/visualization_contract.py`
does not exist, no `visualization/` bundle exists in any result directory, and
`src/ai_trade/server.py` implements the older, superseded
`docs/backend_api_specification.md` instead.

This design does not replace that contract and does not invent a competing
format. It implements a vertical slice of it, in the order the contract itself
prescribes in section 14: build the dashboard against fixtures first, then
connect it to the API.

Two dataset kinds are added. Contract section 2 permits this: specialized zone
reviews and causal diagnostics "may be added as new dataset kinds without
changing the version 1 core objects".

| Dataset kind | Purpose |
| --- | --- |
| `zones` | One-hour supply and demand zone geometry, including competing zones |
| `trade_audit` | Per-trade rule-check results |

`docs/backend_api_specification.md` is marked superseded rather than deleted,
because `dashboard/src/App.tsx` still consumes its endpoints.

## 4. Audit checks

Each check is a pure function over one signal record plus its matching trade
record. A failure means the backtest is wrong, not that the trade was bad.

| ID | Check | Assertion |
| --- | --- | --- |
| `causality_atr` | ATR precedes trigger | `one_hour_atr_timestamp` < `trigger_timestamp` |
| `causality_zone` | Zone qualified first | zone `qualified_timestamp` < `trigger_timestamp` |
| `stop_buffer` | Buffer derivation | `stop_buffer` == 0.05 x `one_hour_atr` |
| `stop_price` | Stop placement | `stop_price` == zone boundary +/- `stop_buffer` |
| `entry_timing` | Entry bar | `entry_timestamp` is the next 15m bar after `trigger_timestamp` |
| `target_price` | Target derivation | `target_price` == entry +/- (entry - stop), `reward_to_risk` == 1.0 |
| `penetration` | v1.1 long gate | longs have `long_zone_penetration_fraction` <= 0.25 |
| `session` | Session window | entry >= 10:30 America/New_York, < 15:00, not Friday |
| `outcome` | Exit consistency | `exit_reason` `stop` implies exit at or beyond stop; `target` implies exit at or beyond target |
| `side_match` | Zone side | demand zone implies long, supply zone implies short |

Numeric comparisons use an absolute tolerance of `1e-6`, matching the
reconciliation tolerance already defined in the visualization contract.

`causality_zone` is not satisfiable from `candidate_signals.csv` as it exists
today. That file records `zone_status` and scores but no qualification
timestamp. The producer must emit it. This is a deliberate argument for the
exporter living inside the producer, where the zone timeline is still in
memory, rather than parsing finished CSVs.

## 5. Data the view requires

Per selected result (strategy version and symbol):

- The full trade ledger. Every trade, with the canonical trade fields already
  present in `fixed_trades.csv`.
- The audit result per trade: check ID, pass or fail, and on failure the
  expected and actual values.
- The zone set per trade: the selected zone, plus any zone that was live and
  overlapping at `trigger_timestamp`. Each carries `zone_id`, side, lower,
  upper, `qualified_timestamp`, and score.
- A one-hour bar window covering zone formation through exit.
- A fifteen-minute bar window covering the trigger bar through exit.

Competing zones are required, not optional. The strategy ranks overlapping
zones by evidence score, then width, then zone ID. Drawing only the winning
zone would make that ranking rule unverifiable, because the chart would be
derived from the same selection being audited.

Bar windows are bounded rather than full series. The window rule is
deterministic so a regenerated fixture is byte-identical:

- One-hour window: from 40 bars before the zone's `qualified_timestamp` through
  10 bars after `exit_timestamp`.
- Fifteen-minute window: from 20 bars before `trigger_timestamp` through 20
  bars after `exit_timestamp`.

Windows are clipped at the ends of the available series. For 38 SPY v1.1 trades
this is roughly 3,800 bars, small enough to ship as a static fixture. Full
series arrive with the backend phase.

## 6. Interface

Three linked regions, all visible at once. Both charts are shown together; they
are not behind a toggle.

### 6.1 Trade list

Every trade in the result. Columns: ordinal, entry timestamp, side, result in R,
outcome, audit status. Outcome and audit status are colour-coded. Selecting a
row drives both charts.

A summary above the list reports how many trades passed all checks and how many
need review. Failing trades are the intended entry point.

### 6.2 One-hour chart, "the setup"

Answers why a trade was allowed to exist.

- The selected zone as a filled band, labelled with its price bounds and score.
- Competing overlapping zones as faint outlines with their scores, so the
  ranking rule is visible.
- A marker at the zone's qualification timestamp.
- The trigger window highlighted.

A qualification marker appearing after the trigger window is a visible
causality failure.

### 6.3 Fifteen-minute chart, "the execution"

Answers what actually happened.

- The trigger candle highlighted.
- Entry, stop, and target as three horizontal price lines.
- A marker at the exit, labelled with which level was hit and the resulting R.

Every drawn value comes from a recorded producer field. Nothing on either chart
is recomputed by the dashboard. If a chart disagrees with the written rules, the
backtest is wrong.

## 7. Delivery phases

### Phase 1 — frontend against a contract-shaped fixture

The frontend design is finalised before any backend work begins.

1. `src/ai_trade/strategy_04_audit.py` provides the section 4 checks as pure
   functions over signal and trade records, with no I/O.
2. A one-time generator script reads the real Strategy 04 result CSVs and the
   cached bar CSVs recorded in `backtest_report.json`, calls those check
   functions, and writes `dashboard/src/fixtures/strategy_04_v1_1_spy.json` in
   the contract's shape.
3. `generateMockBars()` and `MOCK_TRADES_S4` are deleted from
   `dashboard/src/mockData.ts`. The hardcoded metric tables in
   `dashboard/src/strategy04Data.ts` are replaced by fixture-derived values.
4. The trade list, one-hour chart, and fifteen-minute chart are built against
   the fixture.

### Phase 2 — backend

Begins only once the Phase 1 interface is final.

1. `src/ai_trade/visualization_contract.py` implements the contract's canonical
   models, validation, reconciliation, and atomic manifest-last publication.
2. The exporter calls the same `strategy_04_audit.py` functions Phase 1's
   generator used, so the checks are never implemented twice.
3. The Strategy 04 backtest publishes a bundle after writing its existing
   artifacts. Existing CSV and JSON outputs are unchanged, so archives and
   locked baselines stay valid.
4. `server.py` gains `/api/runs`, `/api/runs/{bundle_id}/manifest`,
   `/api/runs/{bundle_id}/datasets/{dataset_id}`, and `/health`. Existing
   endpoints are left in place.
5. The dashboard swaps its data source from the fixture to the catalog. No
   component changes, because the fixture already matched the contract shape.

The result is the intended workflow: change a strategy, run the backtest, and
the run appears in the dashboard with no file edited by hand.

## 8. Testing

- Audit checks: pytest unit tests per check, covering pass, fail, and boundary
  cases. Boundary cases include penetration exactly at 0.25, entry exactly at
  10:30 and 15:00, and same-bar stop and target where stop is assumed first.
- Fixture generator: a test asserting the generated fixture reconciles with
  `backtest_report.json` on trade count, net P&L, and ending equity, so a
  silently wrong fixture cannot pass.
- Charts: rendered from the fixture with no network access in Phase 1.
- Phase 2 adds the contract validation and reconciliation tests already listed
  in the visualization contract, section 13.

## 9. Risks

- The audit and the backtest could share a misreading of the strategy document.
  The checks therefore assert internal consistency of recorded values and
  causal ordering, which are falsifiable independently of rule interpretation.
- The fixture is a point-in-time copy and will drift from the CSVs if a
  backtest is rerun. Phase 2 removes the fixture entirely. Until then the
  reconciliation test detects drift.
- Emitting `qualified_timestamp` and competing zones requires changing the
  Strategy 04 producer's output. Existing artifacts are additive-only, so prior
  results remain readable.
