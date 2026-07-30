# Strategy 04 — Version 1.3

## Purpose

Test whether the directional-body requirement on the trigger candle is
symbol-dependent.

Version 1.3 asks a question; it does not propose a change. The null hypothesis
is that the rule stays on everywhere, and the burden of evidence is on any
symbol that wants it off.

## The rule under test

`_reaction_matches` in `src/ai_trade/strategy_04_v1.py` requires the trigger
candle's body to point in the trade's direction:

```
demand / long  -> bar.close > bar.open
supply / short -> bar.close < bar.open
```

It is already parameterised as
`Strategy04ExecutionParameters.require_directional_body`, default `True`. No
new rule needs writing — this version measures what the existing switch is
worth, per symbol.

Note what the rule is not. A trigger can contact the zone, penetrate it only
shallowly, and close back outside it — satisfying every other Version 1.1
condition — and still be rejected because the candle itself closed against the
trade. The rejected reaction does not consume the zone, so a later valid
reaction may still qualify.

## Motivating observation

Trade 43 of the QQQ v1.1 sample (demand 485.67–486.33, trigger
`2024-09-30T15:15:00Z`) fired once out of 43 zone touches in the preceding
eight days, and lost. Two of the rejected touches penetrated only 17% and 12%
and closed back above demand; both were rejected solely by the
directional-body rule. Simulated under the same execution rules, one would
have lost 1.04R and the other won 0.95R.

That is an anecdote, not evidence, and it is recorded here only to explain
where the question came from.

An exploratory ablation across SPY, QQQ and DIA at fixed risk suggested the
rule is strongly positive on SPY and DIA and negative on QQQ. **Those figures
are deliberately omitted from this document.** They were produced before
commits `2cf1982` and `10f2994` changed the cost model, so they no longer
describe the code as it stands. Implementing this version means measuring
again, not reusing them.

## Required ablation

| Variant | `require_directional_body` |
| --- | --- |
| v1.3-base | `True` (reproduces Version 1.1 exactly) |
| v1.3-off | `False` |

`v1.3-base` must reproduce the current Version 1.1 fixed-risk result for each
symbol, trade for trade. If it does not, the harness is wrong and no other
number in the run may be read.

Run both variants on every symbol with cached one-hour and fifteen-minute
data: SPY, QQQ, DIA, EURUSD, GBPUSD. FX pairs are included because Version 1.1
baselines now exist for them (`d722519`), and a rule that behaves differently
on a 24-hour instrument than on a US-session ETF is exactly the kind of split
this version exists to detect.

Fixed 0.15% risk only. RRMS is not evaluated until a fixed-risk edge is
accepted for that exact symbol and variant, per the existing RRMS policy.

## Relationship to Version 1.2

Version 1.2 tests two other filters — trigger distance from the stop, and
one-hour direction agreement — with its own four-cell ablation.

**These must not be combined into one run.** Three independently togglable
filters produce eight cells, and an effect could no longer be attributed to a
single rule. Version 1.2's four-cell matrix exists precisely to avoid that.

Both versions also modify the same trigger evaluation in `_reaction_matches`.
Version 1.3 should therefore be implemented after Version 1.2 has reported,
and rebased onto whatever Version 1.2 leaves behind, rather than developed
alongside it.

## Rules retained unchanged

Everything else in Version 1.1 stands: one-hour v0.3 zones for location, the
25% long penetration limit, the fifteen-minute reaction, entry at the next
fifteen-minute open, stop beyond the zone by 0.05 × latest completed one-hour
ATR(14), 1R target, session and Friday controls, and fixed 0.15% risk.

## Research warning

The exploratory measurement that motivated this version was in-sample, on the
same data the rules were developed against, and ran one variant per symbol.
It indicates a direction worth testing. It is not a result.

Version 1.1's own history is the governing precedent. Its 25% penetration rule
improved SPY and DIA and reduced QQQ, and was therefore never made universal —
see `results/cross_market/FILTER_VALIDATION_DECISION.md`. If the
directional-body rule splits the same way, that would be **two independent
filters preferring the same instruments**, which is a more interesting finding
than either filter alone and deserves its own investigation before either is
made symbol-conditional.

Two filters agreeing is also the point at which the tempting conclusion —
"QQQ needs its own rule set" — becomes most dangerous, because it can be
reached from a handful of in-sample runs. It requires out-of-sample support.

## Promotion criteria

Version 1.3 may change the rule for a symbol only when, for that exact symbol:

1. Fixed-risk performance beats the incumbent version.
2. The improvement survives out-of-sample testing.
3. Cost and slippage stress does not erase the edge.
4. The result holds after the cost-model change of `2cf1982` and `10f2994`,
   not merely before it.

No configuration is approved for paper or live execution by this document.
