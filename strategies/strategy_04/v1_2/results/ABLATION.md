# Strategy 04 v1.2 ablation -- fixed 0.15% risk

Every number is in-sample. Per the spec, a filter that helps one
symbol must not be adopted for others without its own evidence, and
promotion additionally requires out-of-sample confirmation, parameter
sensitivity, and cost stress. This table attributes effects; it does
not approve anything.

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

