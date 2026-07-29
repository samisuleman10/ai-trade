# Strategy 04 — Version 1.2

## Purpose

Test two independent rejection filters found during the trade-audit review of
Version 1.1. Both address the same observation from different angles: a trigger
candle can satisfy every Version 1.1 rule and still produce a trade whose risk
is large relative to the structure it is based on, or whose direction opposes
the prevailing one-hour candle.

Version 1.2 is an experiment, not a replacement. Version 1.1 remains the
research candidate for SPY and DIA, and Version 1 for QQQ, until this version
proves itself on unseen data.

## Motivating observation

Trade 21 of the SPY sample (trigger `2024-01-03T19:15:00Z`):

```
zone            468.71 – 469.39   width 0.68
trigger candle  O 469.56  H 471.19  L 469.22  C 470.94   bullish
penetration     25.0%   (passed the Version 1.1 limit by zero margin)
entry 471.00    stop 468.64    risk 2.36 = 3.5 x the zone width
outcome         stopped out, -1.02R
```

The trigger low only grazed the zone, so the Version 1.1 penetration rule
allowed it. But the candle spanned 2.9 times the zone width and closed 1.55
above the zone, while the stop stayed anchored to the zone. The trade needed
2.36 of favourable movement to earn 1R from a 0.68-wide structure.

## Filter A — trigger distance from the stop

Reject a signal when the trigger candle closes too far from its own stop,
measured in zone widths.

```
risk_ratio = |trigger close - stop price| / zone width
reject when risk_ratio > max_risk_zone_ratio
```

The boundary value is allowed. A rejected reaction does not consume the zone; a
later valid reaction may still qualify, matching Version 1.1 behaviour.

`trigger close` is used deliberately rather than the entry price. Entry is the
next 15-minute bar's open and is unknown when the decision is made, so a filter
built on it would not be causal. Stop price is already fully determined at
trigger close, since it derives from the zone boundary and the latest completed
one-hour ATR.

`max_risk_zone_ratio` is a parameter, not a constant. See Research warning.

## Filter B — one-hour direction agreement

Reject a signal when the latest completed one-hour candle opposes the trade
direction.

```
reference bar = the one-hour bar identified by one_hour_atr_timestamp
long  requires  reference close >= reference open
short requires  reference close <= reference open
```

The reference bar is the same completed one-hour bar the stop buffer already
uses, so the filter introduces no new data and no new causality risk. Doji bars
(close equal to open) are permitted in both directions.

## Required ablation

The two filters must be evaluated separately before any combination is
considered, so that any effect can be attributed:

| Variant | Filter A | Filter B |
| --- | --- | --- |
| v1.2-base | off | off |
| v1.2-a | on | off |
| v1.2-b | off | on |
| v1.2-ab | on | on |

`v1.2-base` must reproduce Version 1.1 exactly. If it does not, the harness is
wrong and no other result may be read.

Every variant runs on SPY, QQQ, and DIA at fixed 0.15% risk. RRMS is not
evaluated until a fixed-risk edge is accepted for that exact symbol and
variant, per the existing RRMS policy.

## Rules retained unchanged

- One-hour v0.3 zones provide location.
- Fifteen-minute candles provide entry confirmation.
- The Version 1.1 25% long penetration limit stays in force.
- Shorts retain the complete Version 1 trigger logic.
- Entry is the next immediately following 15-minute open.
- Stop is outside the zone by 0.05 × latest completed one-hour ATR(14).
- Target is 1R.
- No entries before 10:30 or from 15:00 America/New_York.
- No Friday entries; positions close before the weekend.
- Fixed risk is 0.15%.

## Producer output required for auditing

`candidate_signals.csv` must gain three columns so the audit tool can verify
these rules from recorded evidence rather than recomputation:

- `risk_zone_ratio` — the Filter A value at decision time
- `one_hour_reference_open` — open of the Filter B reference bar
- `one_hour_reference_close` — close of the Filter B reference bar

Without these the filters are unauditable, repeating the gap that made the
zone-qualification timestamp uncheckable in the first audit build.

## Research warning

The `max_risk_zone_ratio` threshold has **not** been established. An
exploratory split at 2.5 over the combined Version 1 and Version 1.1 fixed-risk
results showed:

| Bucket | Trades | Win rate | Average R |
| --- | ---: | ---: | ---: |
| ratio ≤ 2.5 | 259 | 58.3% | +0.123 |
| ratio > 2.5 | 44 | 47.7% | −0.075 |

This figure must not be treated as a validated edge, for three reasons:

1. The 2.5 split was chosen after inspecting the same data it is measured on.
2. Version 1 and Version 1.1 share most of their trades, so the 303 rows are
   far fewer independent observations than the count suggests.
3. The rejected group contains only 44 trades.

The threshold must therefore be selected by a parameter sweep with sensitivity
reporting, exactly as the existing validation workflow requires, and confirmed
out of sample before use.

Filter B has **no supporting measurement at all** yet. It is a hypothesis drawn
from a single reviewed trade and must be treated as such.

Version 1.1's own history is the governing precedent: its 25% rule improved SPY
and DIA but reduced QQQ performance, and was therefore never made universal.
A filter that helps on one symbol must not be adopted for the others without
its own evidence.

## Promotion criteria

Version 1.2 may become the research candidate for a symbol only when, for that
exact symbol and variant:

1. Fixed-risk performance beats the incumbent version.
2. The improvement survives out-of-sample testing.
3. Parameter sensitivity shows the result is not a threshold artefact.
4. Cost and slippage stress does not erase the edge.

No configuration is approved for paper or live execution by this document.
