# Strategy Specifications

This folder contains the version-controlled source of truth for individual
trading strategies.

Each strategy file is intentionally both human-readable and structured enough
to become the basis for configuration, backtests, implementation tasks, and
future AI-assisted analysis. It must define rules; it must not rely on a chart
image or discretionary interpretation.

The Word design document explains the wider system architecture. These Markdown
files define the strategies that run inside it.

## Lifecycle

```text
draft -> specified -> backtest -> shadow -> paper -> limited_live -> retired
```

A strategy may only move to the next status after its documented acceptance
criteria are met. No strategy file authorizes live trading by itself.
