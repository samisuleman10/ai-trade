# Strategy 04 one-hour indicator — initial SPY review

Status: private research prototype. No trade or order logic exists.

## Dataset

- Source: cached validated IBKR SPY OHLCV.
- Timeframe: one hour.
- Bars: 9,189.
- Range: 2021-04-19 through 2026-07-16.

## Output

| Measure | Initial result |
| --- | ---: |
| Raw zones | 810 |
| Qualified confluence zones | 779 |
| Demand zones | 360 |
| Supply zones | 419 |
| Zones touched at least once | 631 |
| Zones with a verified role-flip retest | 508 |
| Average touch episodes per qualified zone | 2.45 |
| Score 2 | 177 |
| Score 3 | 282 |
| Score 4 | 257 |
| Score 5 | 63 |
| Availability-time violations | 0 |
| Trade signals | 0 |
| Orders | 0 |

## First finding

The initial volume-reference rule is probably too permissive:

- 776 of the 779 qualified zones received volume confluence.
- A nearby POC, VAH, or VAL currently contributes the same single volume point.
- This makes score two relatively easy to achieve for a pivot or order block.

This is not yet a reason to tune parameters for a better-looking result. The
saved historical charts must first be inspected to decide whether:

1. Only POC should contribute score.
2. VAH and VAL should be visual context only.
3. Volume distance should be smaller than 0.30 ATR.
4. A volume reference should contribute only when it comes from a session
   earlier than the zone origin.
5. The minimum score should remain two or increase to three.

## Files

- `indicator_report.json`: parameters, safety flags, and summary.
- `all_zones.csv`: all raw candidates and final lifecycle state.
- `qualified_zones.csv`: zones that reached the minimum score.
- `zone_events.csv`: chronological creation, merge, qualification, touch,
  rejection, break, flip, and expiry events.
- `volume_references.csv`: causal session POC/VAH/VAL approximations.
- `zone_review/index.html`: saved visual review containing twelve historical
  examples.

## Next gate

The Python engine is mechanically validated, but the indicator is not visually
approved. Review the twelve saved charts and classify each zone as:

- Correct and useful.
- Correct but too broad.
- Correct but too late.
- Incorrect merge.
- Weak/unnecessary volume qualification.
- Incorrect lifecycle label.

Only after that review should v0.2 change the formulas.
