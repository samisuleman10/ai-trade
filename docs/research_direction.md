# Research direction: universal rules, per-instrument rules, and sample size

Written 30 July 2026, after Strategy 04 v1.2's filter results.

## The question

Strategy 04's filters keep behaving differently on different instruments. The
25% penetration rule helps SPY and DIA and hurts QQQ. v1.2's Filter B does the
reverse. The directional-body requirement splits like the penetration rule.

The natural reading is that there is no universal strategy, that each
instrument needs its own rules, and that research should therefore specialise:
one strategy, one instrument, locked, then improved.

This note argues that the reading is premature, that the proposed remedy would
make the underlying problem worse, and that a different form of focus is
supported by the same evidence.

## What the evidence actually says

Per-trade R on the recorded Strategy 04 v1.1 fixed-risk ledgers:

| Sample | Trades | Average R | t |
| --- | ---: | ---: | ---: |
| SPY | 38 | +0.2184 | +1.38 |
| DIA | 49 | +0.1770 | +1.26 |
| QQQ | 59 | +0.0190 | +0.15 |
| EURUSD | 243 | −0.0728 | −1.13 |
| GBPUSD | 260 | −0.1192 | −1.91 |
| **Pooled equities** | **146** | **+0.1239** | **+1.51** |
| **Pooled FX** | **503** | **−0.0968** | **−2.16** |

Two things follow.

**No individual instrument reaches the conventional |t| ≈ 2.** Not one. The
differences between instruments are differences between figures that are
themselves indistinguishable from zero. At these sample sizes, "SPY and QQQ
disagree" and "we flipped a coin 38 times" produce the same evidence.

**The only result in this project that clears the bar is pooled FX, and it is
negative.** 503 trades, −0.0968R, t = −2.16. It says Strategy 04 loses money on
EURUSD and GBPUSD with the kind of confidence nothing else here has.

That result was only visible because the samples were pooled. Examined
separately, EURUSD sits at −1.13 and GBPUSD at −1.91 and neither concludes
anything.

## Why per-instrument specialisation is the wrong response

Specialising shrinks the evidence exactly where it is already too thin.

Strategy 04 currently has 649 recorded trades across five instruments. Adopt
one-strategy-per-instrument and every future decision rests on 38 to 59 trades
for the equities. That is permanently below the threshold at which any question
can be settled, and each instrument would accumulate filters fitted to its own
noise with no way to distinguish them from filters fitted to its character.

That path has already been walked. Three filters were derived from inspecting
SPY — the 25% rule from the SPY long-loss review, v1.2's Filter A from SPY
trade 21, Filter B from a SPY trade 1 observation. All three improve SPY.
Filters found on an instrument improving that instrument is the expected
signature of fitting, not evidence of instrument character. QQQ has effectively
been serving as an unacknowledged out-of-sample check, and it keeps failing
them.

Formalising per-instrument rules would convert that pattern from an accident
into a method.

## Which instrument differences are real

Some are structural and need no statistical proof:

- FX trades around the clock, so session-window rules mean something different
  than they do on a US-session ETF.
- MGC carries a 10× contract multiplier, front-month rollover, margin and
  delivery mechanics. IBKR also refuses to paginate `CONTFUT` history backward,
  capping its 15-minute cache at roughly three months.
- Tick sizes, spreads and commission models differ per venue and instrument.

These justify per-instrument **execution modelling**. They do not justify
per-instrument **signal rules** discovered from a few dozen trades. The
distinction matters: the first is accounting for known mechanics, the second is
inventing rules to fit noise.

## The form of focus worth adopting

Focus on fewer instruments in order to accumulate statistical power — not
because instruments need different rules.

Under that reasoning the candidate is not SPY. FX generates six times the
trades per year of cached data because it trades continuously. Whatever is
learned there will be learned with enough evidence to believe it, and the
pooled FX result is already the only conclusion in this repository that meets
the usual standard.

The uncomfortable part is that the conclusion is negative. That is not a reason
to look elsewhere. It may be the first honest answer this research has
produced, and it points toward "this approach does not work on these
instruments" rather than "this approach needs a fourth filter."

## Recommended sequence

1. **Do not lock anything yet.** Locking is the right discipline, but locking a
   configuration that has not cleared a holdout makes the fitting permanent and
   harder to revisit. Lock after validation, not before.
2. **Run v1.3 as specified** — freeze every rule found so far, strict
   chronological holdout, decision rule committed in advance, FX first because
   that is where the evidence is.
3. **Pool where instruments are comparable.** Report per-instrument results for
   diagnosis, but judge on pooled samples where the instruments share a venue
   and session structure. Pooling is what made the FX result visible.
4. **Treat per-instrument rule differences as a hypothesis requiring
   out-of-sample support**, not as an observation. Two instruments as correlated
   as SPY and QQQ needing opposite rules should be a warning, not a finding.

## Caveats on this note's own evidence

- Pooling EURUSD and GBPUSD does not give 503 independent observations. Both
  are USD crosses and move together, so the effective sample is smaller than
  the count and the true t is weaker than −2.16. It remains the strongest
  result here, but it is not as strong as the number alone suggests.
- The t-test assumes independent trades. Approximately true, since only one
  position is open at a time.
- No adjustment is made for the several filters already examined. Adjusting
  would make every figure above less favourable, not more.
- All of this is in-sample. It is a reason to run a holdout, not a substitute
  for one.
