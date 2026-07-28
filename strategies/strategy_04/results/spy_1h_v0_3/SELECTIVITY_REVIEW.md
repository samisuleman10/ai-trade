# Strategy 04 v0.3 selectivity review

## Dataset

- SPY one-hour bars
- 9,189 bars
- 2021-04-19 through 2026-07-16
- No trade signals or orders

## Comparison

| Measure | v0.1 | v0.2 | v0.3 |
| --- | ---: | ---: | ---: |
| Qualified zones | 779 | 485 | 177 |
| Demand zones | 360 | 215 | 77 |
| Supply zones | 419 | 270 | 100 |
| Rejection events | 2,851 | 1,592 | 252 |
| Volume-confluence events | 776 | 296 | 71 |
| Frozen-geometry violations | Not measured | 0 | 0 |
| Availability/look-ahead violations | 0 | 0 | 0 |

Version 0.3 is intentionally more selective. Its reduction does not establish
profitability; it shows that the repeated-pivot and staged-rejection rules are
filtering the visual noise identified in TradingView.

## Qualification composition

- 177 qualified zones.
- 77 demand and 100 supply.
- 28 already contained POC evidence at qualification.
- 71 zones received additional independent evidence after qualification.
- Qualification scores:
  - Q2: 73
  - Q3: 75
  - Q4: 27
  - Q5: 2

## Visual review

Thirty zones were selected deterministically across the complete v0.3
sequence. Open `zone_review/index.html`.

Audit legend:

- T: valid approach followed by a touch.
- R: later directional rejection confirmation.
- B: break.
- F: verified role flip.
- U: evidence upgrade after qualification.

## Remaining gate

1. Compile Pine v0.3 in TradingView.
2. Inspect the Clean view.
3. Review all thirty Python examples.
4. Reconcile at least twenty common Pine/Python zones.
5. Freeze the one-hour engine before adding 15-minute execution logic.
