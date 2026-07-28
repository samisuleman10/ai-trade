# Standard strategy research workflow

Every strategy version must follow this deterministic sequence:

1. Load validated local market-data caches. Do not redownload unchanged data.
2. Generate causal signals with no current-bar or future-bar look-ahead.
3. Run the same trade path under both sizing modes:
   - fixed 0.15% account risk;
   - RRMS risk progression.
4. Save `fixed_trades.csv`, `rrms_trades.csv`, both JSON summaries, and `backtest_report.json`.
5. Report fixed and RRMS results together: trades, win rate, net P&L, profit factor, average R, and maximum drawdown.
6. Run `ai_trade.strategy_review_workflow` to create:
   - `review_summary.md` comparing fixed and RRMS;
   - at least ten deterministic SVG trade-setup charts sampled across the ledger;
   - interactive fixed and RRMS trade reviews;
   - a workflow manifest identifying all inputs and outputs.
7. Inspect entries, stops, targets, exits, and indicator state visually before accepting or modifying the strategy.
8. A positive RRMS result does not validate a strategy whose fixed-sizing average R or profit factor is negative.

Example post-processing command:

```powershell
.venv/Scripts/python.exe -m ai_trade.strategy_review_workflow `
  --report <run>/backtest_report.json `
  --bars <market-data.csv> `
  --fixed-trades <run>/fixed_trades.csv `
  --rrms-trades <run>/rrms_trades.csv `
  --output <run>/review `
  --symbol SPY `
  --timeframe 4h `
  --chart-count 10
```
