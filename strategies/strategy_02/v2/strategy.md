# Strategy 02 v2 — VIX filter

Strategy 2 v2 preserves every locked v1.5 rule and adds one condition:

> A trade is allowed only when the latest **completed 15-minute VIX close is
> strictly below 20.00** at the 1-hour confirmation / 15-minute entry decision.

The VIX bar must have closed before or exactly at the decision time. This makes
the filter causal in both backtests and a live evaluator. VIX `20.00` or above
rejects both long and short candidates.
