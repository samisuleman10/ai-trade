# Standard strategy research workflow v2

Every reported strategy table must show both fixed 0.15% risk and RRMS, with:

- total trades, wins, and losses;
- long wins/losses and short wins/losses;
- weekend-close count and weekend wins/losses;
- stop and target exit counts;
- net P&L, profit factor, average R, and maximum drawdown;
- maximum consecutive losses;
- average holding time and maximum RRMS tier;
- at least ten saved trade-setup charts plus interactive fixed/RRMS reviews.

Run `python -m ai_trade.strategy_review_workflow_v2` after each backtest. The
workflow reads the saved ledgers deterministically; it does not recalculate or
change signals.
