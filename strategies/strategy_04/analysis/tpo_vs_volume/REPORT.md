# TPO vs volume profile weighting - equity bridge report

How far time-at-price weighting diverges from volume weighting on the
symbols where both exist. Read this before interpreting any spot-FX
run: FX zones are TPO-qualified, and this table is the only measured
link between TPO behaviour and the volume-weighted equity results.

| Symbol | Zones (vol) | Zones (time) | Shared | Signals (vol) | Signals (time) | Shared |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 177 | 178 | 176 | 93 | 92 | 92 |
| QQQ | 215 | 215 | 215 | 113 | 113 | 113 |
| DIA | 208 | 208 | 206 | 95 | 95 | 95 |

**Caveat:** this report measures profile-weighting divergence only, on equity data where both weightings can be computed. It cannot cover the FX session-length / bar-scale mismatch: v0.3's bar-count parameters (`volume_reference_max_age_bars`, `max_zone_age_bars`, `broken_retest_window_bars`, etc.) were tuned on ~7-bars/session equity RTH data, while FX sessions run ~24 bars/session -- roughly 3.4x tighter in wall-clock terms. A small weighting divergence here does not mean the FX runs are validated against that separate, unmeasured mismatch.
