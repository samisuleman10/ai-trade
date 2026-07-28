---
title: Streamlit Strategy Research Library
status: proposed
owner: Sami
first_proposed: 2026-07-28
---

# Streamlit Strategy Research Library

## Idea

Build a local Streamlit interface that becomes the visual catalogue for all
strategy research. It should make Strategy 1, Strategy 2, Strategy 3, every
version, every tested asset and timeframe, and all saved evidence easy to
browse from one place.

This is initially a **read-only research application**, not an order-execution
screen.

## Main navigation

`Strategy → Version → Symbol or asset → Timeframe → Backtest run`

## Information shown

### Strategy definition

- Strategy purpose and current status.
- Complete entry, confirmation, stop-loss, take-profit, and exit rules.
- Indicators and exact parameters.
- Session restrictions, Friday/weekend handling, and risk-management rules.
- Differences from the previous version.
- Known limitations and unresolved questions.

### Backtest evidence

- Market-data source, cached dataset, timeframe, and date range.
- Number of trades and wins/losses.
- Fixed-risk and RRMS results side by side.
- Win rate, net P&L, profit factor, average R, and maximum drawdown.
- Long versus short performance.
- Weekend exits, stop-loss exits, take-profit exits, costs, and assumptions.
- Out-of-sample, walk-forward, and Monte Carlo status when those tests exist.

### Visual trade review

- Gallery of saved candlestick charts.
- Alligator and other indicators used by that strategy.
- Entry, stop loss, take profit, exit, and exit reason.
- Links to the complete interactive fixed-risk and RRMS trade ledgers.

### Comparisons and decisions

- Compare versions of the same strategy.
- Compare symbols, assets, and timeframes without duplicating rows.
- Identify promising research candidates while keeping them separate from
  approved shadow, paper, or live strategies.
- Save the reason a strategy was promoted, paused, rejected, or archived.

## Status model

1. Draft
2. Implemented
3. Backtested
4. Visually reviewed
5. Shadow candidate
6. Paper candidate
7. Rejected or archived

`Live-ready` must remain a separate status requiring explicit approval.

## Proposed architecture

Streamlit is only the presentation layer. Existing deterministic Python code
continues to handle:

- Cached market data.
- Indicator calculations.
- Signal generation.
- Backtesting and position sizing.
- Statistics.
- Chart generation.

The UI reads the files produced by those workflows:

- Strategy Markdown specifications.
- `strategy_manifest.json` metadata.
- Backtest report and summary JSON files.
- CSV trade ledgers.
- Saved SVG/PNG trade charts.
- Interactive HTML trade reviews.

It must not recalculate results differently or invent missing statistics.

## Automation design

Add one normalized `strategy_manifest.json` to every strategy version. A
registry loader discovers those manifests and automatically creates the
Streamlit navigation. New strategy versions should appear after the normal
research workflow runs, without building a custom page each time.

## Suggested first release

1. Strategy/version browser.
2. Rules and version-change page.
3. Compact cross-symbol/timeframe results table.
4. Fixed-risk versus RRMS comparison.
5. Saved chart gallery.
6. Links to ledgers, reports, and source files.

## Later extensions

- Parameter-test comparison.
- Out-of-sample and walk-forward panels.
- Monte Carlo results.
- Shadow and paper-trading monitoring.
- Experiment notes and approval history.
- Macro regime linked to each test.

## Execution boundary

The first release must not contain broker credentials, live-order buttons, or
order-submission authority. Research, monitoring, and execution remain separate
until the execution layer is explicitly designed and approved.

## Next design step

Define the normalized strategy-manifest schema and map the existing Strategy
1–3 folders and output files into it before writing the Streamlit interface.
