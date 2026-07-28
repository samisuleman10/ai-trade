---
strategy_id: strategy_04
component: one_hour_indicator
version: 0.2
status: private_validation
created: 2026-07-28
---

# Strategy 04 one-hour indicator specification v0.2

## Purpose

Version 0.2 corrects the causal-display and zone-clutter issues found during
the first TradingView review of v0.1. It remains a one-hour indicator only:
there are no 15-minute entries, trade signals, orders, or broker actions.

## Changes from v0.1

1. A zone's boundaries, score, side, sources, and timestamp are snapshotted
   when it first qualifies.
2. Later evidence does not rewrite the qualified geometry or qualified score.
   It is recorded as an evidence-upgrade event at the bar where it appeared.
3. Touch, rejection, break, role-flip, and evidence-upgrade markers are drawn
   on their actual event bars.
4. A verified role flip begins a new visual segment at the verification bar;
   it does not recolour the earlier zone history.
5. Clean mode shows the nearest configurable number of demand and supply
   zones, subject to an ATR-distance filter.
6. Audit mode retains the complete causal lifecycle.
7. Only prior-session POC can add volume confluence. VAH and VAL remain
   optional visual context.
8. POC must fall inside the zone to score; proximity alone is insufficient.

## Locked v0.2 defaults

| Parameter | Value |
| --- | ---: |
| Minimum confluence score | 2 |
| POC scoring distance | 0.00 ATR |
| Volume reference maximum age | 8 one-hour bars |
| Clean-mode maximum distance | 2.00 ATR |
| Nearest zones per side | 2 |
| Clean-mode displayed history | 80 bars |
| Lifecycle event markers | On |
| Volume reference lines in Clean mode | Off |

All other calculation defaults remain unchanged from v0.1.

## Label legend

- `Q2` or `Q3`: score frozen at qualification.
- `C2` through `C5`: current evidence score shown only in the live status
  label.
- `T`: first bar of a zone contact.
- `R`: rejection confirmed on that bar.
- `B`: zone broken on that bar.
- `F`: broken zone verified in the opposite role on that bar.
- `U`: independent evidence added after qualification.

## Causal contract

- The qualified box never expands backward after qualification.
- The qualified score never changes.
- Later evidence is timestamped and cannot improve an earlier decision.
- A role flip creates a new visual segment beginning at the flip bar.
- Expired drawings stop at their expiry bar.
- Python validates that final frozen boundaries still equal the qualification
  snapshot for every qualified zone.

## Validation gate

Before adding 15-minute entries:

1. The Pine v0.2 script must compile and render on SPY one-hour standard
   candles.
2. Thirty saved Python examples must be reviewed.
3. At least twenty common Pine/Python zones must be reconciled.
4. Any incorrect merge, timestamp, event, or role flip must be resolved.
5. The one-hour rules are then frozen for the first 15-minute experiment.
