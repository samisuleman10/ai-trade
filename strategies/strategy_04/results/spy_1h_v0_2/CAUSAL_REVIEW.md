# Strategy 04 v0.2 causal review

## Dataset

- Instrument: SPY
- Timeframe: one hour
- Bars: 9,189
- Range: 2021-04-19 through 2026-07-16
- Trade signals: disabled
- Orders: disabled

## v0.1 versus v0.2

| Measure | v0.1 | v0.2 |
| --- | ---: | ---: |
| Raw zones | 810 | 786 |
| Qualified zones | 779 | 485 |
| Demand zones | 360 | 215 |
| Supply zones | 419 | 270 |
| Volume-confluence events | 776 | 296 |
| Qualified with volume already present | Not snapshotted | 163 |
| Frozen-geometry violations | Not measured | 0 |
| Availability/look-ahead violations | 0 | 0 |

The reduction in qualified zones is intentional. In v0.1, almost every zone
eventually received volume confluence. In v0.2, only prior-session POC scores,
and POC must fall inside the zone.

## Qualification snapshots

- 485 qualified zones.
- 285 qualified at Q2.
- 200 qualified at Q3.
- 303 received additional evidence after qualification.
- Later evidence is recorded but does not rewrite the qualified score or
  geometry.

## Saved visual review

Thirty zones were selected deterministically across the complete qualified
zone sequence. Open `zone_review/index.html` to inspect them.

Legend:

- T: touch
- R: rejection
- B: broken
- F: verified role-flip retest
- U: evidence received after qualification

## Interpretation

Version 0.2 is more selective and its saved data passes the automated causal
checks. This is not evidence of profitability: no 15-minute triggers, trades,
costs, or exits exist yet.

The next gate is visual reconciliation:

1. Confirm Pine v0.2 compiles on SPY one-hour candles.
2. Inspect the thirty saved examples.
3. Match at least twenty Pine zones to Python zones.
4. Resolve any boundary, score, event-time, or role-flip mismatch.
5. Freeze the one-hour indicator before implementing 15-minute entries.
