---
name: strategy-research
description: Use when starting a new trading strategy, a new version of an existing strategy, or adding an instrument to one — any work in this repo that ends in backtest results, published dashboard runs, or a promotion decision.
---

# Strategy research lifecycle: spec to dashboard

Every strategy version follows the same pipeline. The reference implementation is Strategy 04 v1.2 (built 2026-07-30) — when in doubt, read those files instead of inventing.

**Core principle: a result nobody can independently verify from recorded evidence does not exist.**

## Phases and gates

**1. Spec before code.** Write `strategies/strategy_XX/vY/strategy.md` first: hypothesis with motivating evidence, exact rules, required ablation table, research warnings naming every in-sample parameter, promotion criteria. Exemplar: `strategies/strategy_04/v1_2/strategy.md`.

**2. Plan, then subagent execution.** Brainstorm scope → writing-plans (complete code in tasks) → subagent-driven-development with per-task reviews and a final whole-branch review. Variants and filters are parameter configurations of ONE signal module — never copies of the loop (copies drift; the RRMS cost-duplication bug cost a full rerun).

**3. Non-negotiable gates before reading any result:**
- **Incumbent parity:** if a version claims "base ≡ incumbent", an independent script must prove it byte-for-byte (signals minus new columns, trades exactly) per symbol. Parity fails ⇒ the harness is wrong; stop; nothing else may be read. Exemplar: `src/ai_trade/verify_strategy_04_v1_2.py`.
- **Auditable columns:** every rule's decision value is recorded in `candidate_signals.csv` at decision time and recomputed by the verifier from evidence (causality included: reference timestamps ≤ decision time).
- **Thresholds are swept, never chosen by code.** Sensitivity tables per symbol; the report is evidence for a human. Exemplar: `src/ai_trade/sweep_strategy_04_v1_2_risk_ratio.py`.
- **Per-symbol evidence only.** A filter that helps one symbol is not adopted elsewhere (v1.2's Filter B: +$1,328 QQQ, −$1,638 SPY).

**4. Landing on the dashboard.** Write the standard six files (`candidate_signals.csv`, `fixed_trades.csv`, `fixed_summary.json`, `rrms_trades.csv`, `rrms_summary.json`, `backtest_report.json` with `strategy_id`) and call `publish_result_directory()` — the run appears in All runs automatically (bundle id from path). New instruments must reuse the committed baseline's exact config + indicator dispatch (see `symbol_run_inputs` in `src/ai_trade/backtest_strategy_04_v1_2_asset.py`); config drift invalidates every comparison.

**5. Deep-dive UI (per strategy, manual).** New version ⇒ version chip + spec entry (variant row if ablation); new strategy with its own deep-dive ⇒ it becomes the FIRST/default tab (newest strategy first, like version chips). Check `strategyDescriptions.ts` has a condition entry; `npx tsc --noEmit` clean. Exemplar commit: `1707e4d`.

**6. Research record.** Commit results + ablation/sweep artifacts with caveats written INTO the files; every report carries a warning naming unvalidated parameters; update auto-memory. Promotion always requires out-of-sample confirmation — in-sample tables approve nothing.

## Red flags — stop and re-read the exemplars

- "Base is close enough to the incumbent"
- A threshold picked because the backtest liked it
- A second copy of the signal loop or cost computation
- Results published whose filters can't be re-verified from the CSV
- Adopting a filter on all symbols because it worked on one
