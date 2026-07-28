---
title: Trading Tools Watchlist
status: living_reference
owner: Sami
last_updated: 2026-07-18
---

# Trading Tools Watchlist

This is a parking place for trading tools, platforms, MCP servers, and ideas
seen online. Adding an item here is **not** an approval to buy, install,
connect credentials, or use it for trading.

For each tool, decide later whether to:

1. Use it as-is.
2. Integrate a limited part of it.
3. Build the capability ourselves.
4. Keep it only as a reference and do nothing.

## Evaluation checklist

Before adopting any tool, record:

- Primary purpose and asset classes.
- Data source, quality, ownership, and historical coverage.
- Broker/exchange support and whether it supports IBKR or MEXC.
- Backtesting assumptions, fees, slippage, and no-lookahead protections.
- Paper/live execution authority and key-permission controls.
- Cost, licence, hosting, privacy, and vendor-lock-in risks.
- What it adds beyond the existing local Python research stack.
- Decision: watch / evaluate / use / integrate / build ourselves / reject.

---

## Jesse Trade MCP

| Field | Notes |
| --- | --- |
| Website | <https://jesse.trade/pricing> |
| Category | Trading research, backtesting, optimisation, and crypto exchange execution platform with an MCP/agentic workflow offering. |
| First seen | 2026-07-18 |
| Current decision | **Watch / evaluate later. Do not connect credentials or install yet.** |
| Potential project fit | Could be useful for future crypto spot/perpetual-futures research, optimisation, Monte Carlo testing, and paper-trading workflows. |
| Current project fit | Does not replace the local IBKR/SPY research and shadow-trading stack. The pricing page lists crypto exchange routes; IBKR is not listed there. |
| Why it is interesting | Its site advertises backtesting, research, optimisation, Monte Carlo, machine-learning features, and MCP agentic-workflow limits. |
| Important caution | Treat its backtest and execution engine as a separate system. We must validate its data, fees, slippage, exchange support, and order permissions before comparing results with our own code. |
| Pricing snapshot | The page currently lists a free tier, plus lifetime Basic ($899), Pro ($999), and Enterprise ($1,599) tiers. Features and prices may change; verify before spending. |
| Questions before evaluation | Does it support MEXC directly? Can it run custom Python strategy logic? Can it import our saved MEXC data? How does its MCP authenticate and what execution authority can be restricted? |
| Next action | When crypto strategy work becomes active, read its official docs and exchange list, test only in a sandbox/testnet, and compare one strategy against our local reproducible backtest. |

---

## Local Multi-Chart Workspace (Lightweight Charts reference)

| Field | Notes |
| --- | --- |
| Reference | YouTube concept: local multi-chart dashboard built with TradingView Lightweight Charts, a small Python/Flask backend, and pluggable market-data adapters. |
| First seen | 2026-07-18 |
| Category | Visualisation, monitoring, and discretionary chart-review workspace. It is not a strategy engine or an execution system by itself. |
| Current decision | **Watch / build later. Do not start before a strategy has earned a need for live visual monitoring.** |
| Potential project fit | A local AI Trade Chart Workspace for SPY 1h, 15m, and 5m panels; Alligator/Heikin-Ashi overlays; macro-bias badge; and signal, entry, stop, target, and position-size preview. |
| Data decision | For an IBKR strategy, charts and strategy calculations should use the same IBKR bars. Do not use Yahoo/yfinance as the trading-decision feed. |
| What the prompt actually builds | Responsive chart layout, per-panel symbol/timeframe selection, a pluggable data adapter, and live data plumbing. It does **not** specify the formulas or code for Alligator, RSI, FVG, volume profile, or other indicators. |
| Indicator implementation | Lightweight Charts renders lines/bars; the backend/frontend must calculate each indicator from raw OHLCV data or obtain it from an indicator library. Our project already calculates Alligator, Heikin-Ashi, and ATR in Python. New indicators should be independently documented, coded, and tested before being shown or used in a rule. |
| Important caution | A polished live chart does not validate an indicator, data feed, strategy, or broker order flow. It is an observability tool and must remain separate from execution permissions. |
| Future build gate | Begin only after a validated strategy is in sustained shadow mode or paper mode, when manual visual review becomes a genuine workflow need. |

## New tool template

### Tool name

| Field | Notes |
| --- | --- |
| Website |  |
| Category |  |
| First seen |  |
| Current decision | Watch / evaluate / use / integrate / build / reject |
| Potential project fit |  |
| Data and execution concerns |  |
| Cost / licence |  |
| Questions before evaluation |  |
| Next action |  |
