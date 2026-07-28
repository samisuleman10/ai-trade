# Strategy 03 v1 — capped five-loss RRMS rule

Status: historical research only. No order submission is enabled.

1. Risk tiers are `0.15%`, `0.35%`, `0.70%`, `1.50%`, and `1.50%`.
2. Every exit with negative net P&L counts as a loss, including a losing Friday/weekend close.
3. Any profitable exit resets the next trade to `0.15%`.
4. After the fifth consecutive loss, the next trade resets to `0.15%`.
5. The sequence carries across weeks; there is no weekly reset.

Fixed `0.15%` sizing remains the primary measure of whether the signal has an edge. This RRMS variant changes position size, not the underlying entry and exit expectancy.
