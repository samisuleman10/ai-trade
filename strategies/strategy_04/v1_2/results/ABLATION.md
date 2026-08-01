# Strategy 04 v1.2 ablation -- fixed 0.15% risk

**Not every number here is in-sample.** v1.2's rules were fixed at 2026-07-29 10:58 (bffe4f2, the v1.2 spec).

- In-sample: SPY, QQQ, DIA. This data was already in the repository when the rules were written.
- Cross-instrument holdout: IWM, GLD, SLV, EURUSD, GBPUSD. Each arrived afterwards (IWM 2026-07-31 16:40 (55f381e), GLD 2026-07-31 16:40 (55f381e), SLV 2026-07-31 16:40 (55f381e), EURUSD 2026-07-29 23:17 (6c503e4), GBPUSD 2026-07-29 23:17 (6c503e4)), so no rule here could have been fitted to it.

A large delta on a holdout symbol is a claim to be scored under a decision rule, not
a result. Net P&L deltas in this table are neither.

The holdout symbols are scored in `strategies/strategy_04/v1_3/results/HOLDOUT_RESULT.md`.

Per the spec, a filter that helps one symbol must not be adopted for
others without its own evidence, and promotion additionally requires
out-of-sample confirmation, parameter sensitivity, and cost stress.
This table attributes effects; it does not approve anything.

Filter A rows use max_risk_zone_ratio = 2.5, an in-sample, unvalidated threshold -- see the sweep.

FX rows (EURUSD/GBPUSD) are TPO-zone, midpoint-data, modelled-spread runs with equity-tuned bar-count windows and are not comparable 1:1 with equity rows.

## SPY

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 93 | 38 | 0.632 | +0.2184 | +1244.92 | +0.00 |
| a | 79 | 34 | 0.647 | +0.2419 | +1232.53 | -12.39 |
| b | 54 | 18 | 0.444 | -0.1483 | -393.20 | -1638.11 |
| ab | 43 | 14 | 0.500 | -0.0370 | -73.95 | -1318.87 |

## QQQ

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 113 | 59 | 0.525 | +0.0190 | +163.06 | +0.00 |
| a | 105 | 61 | 0.525 | +0.0140 | +119.77 | -43.29 |
| b | 64 | 35 | 0.657 | +0.2850 | +1490.77 | +1327.71 |
| ab | 51 | 32 | 0.625 | +0.2157 | +1032.45 | +869.39 |

## DIA

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 95 | 49 | 0.612 | +0.1770 | +1295.23 | +0.00 |
| a | 85 | 51 | 0.588 | +0.1248 | +950.64 | -344.58 |
| b | 56 | 31 | 0.677 | +0.3066 | +1427.54 | +132.31 |
| ab | 43 | 27 | 0.704 | +0.3569 | +1445.32 | +150.10 |

## IWM

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 100 | 41 | 0.585 | +0.1376 | +840.07 | +0.00 |
| a | 89 | 45 | 0.511 | -0.0133 | -95.69 | -935.76 |
| b | 61 | 24 | 0.458 | -0.1176 | -421.39 | -1261.46 |
| ab | 55 | 26 | 0.538 | +0.0419 | +158.50 | -681.57 |

## GLD

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 68 | 36 | 0.417 | -0.2483 | -1333.52 | +0.00 |
| a | 62 | 35 | 0.457 | -0.1561 | -816.41 | +517.11 |
| b | 42 | 19 | 0.632 | +0.2037 | +578.52 | +1912.04 |
| ab | 40 | 19 | 0.632 | +0.2037 | +578.52 | +1912.04 |

## SLV

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 73 | 34 | 0.471 | -0.1530 | -779.49 | +0.00 |
| a | 64 | 33 | 0.545 | -0.0108 | -56.90 | +722.59 |
| b | 43 | 19 | 0.474 | -0.1611 | -460.37 | +319.13 |
| ab | 37 | 19 | 0.474 | -0.1611 | -460.37 | +319.13 |

## EURUSD

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 291 | 243 | 0.514 | -0.0728 | -2644.78 | +0.00 |
| a | 259 | 218 | 0.509 | -0.0928 | -3012.96 | -368.18 |
| b | 181 | 141 | 0.461 | -0.1797 | -3745.11 | -1100.32 |
| ab | 152 | 119 | 0.454 | -0.2016 | -3548.47 | -903.68 |

## GBPUSD

| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 310 | 260 | 0.496 | -0.1192 | -4572.64 | +0.00 |
| a | 281 | 231 | 0.463 | -0.1954 | -6572.91 | -2000.27 |
| b | 205 | 175 | 0.457 | -0.1966 | -5049.76 | -477.12 |
| ab | 170 | 148 | 0.432 | -0.2535 | -5487.94 | -915.30 |

