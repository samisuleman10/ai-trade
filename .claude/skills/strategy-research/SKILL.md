---
name: strategy-research
description: Use when starting a new trading strategy, a new version of an existing strategy, or adding an instrument to one — any work in this repo that ends in backtest results, published dashboard runs, or a promotion decision.
---

# Strategy research lifecycle: spec to dashboard

Every strategy version follows the same pipeline. The reference implementation is Strategy 04 v1.2 — when in doubt, read those files instead of inventing.

**Core principle: a result nobody can independently verify from recorded evidence does not exist.**

## What is pipeline and what is yours to write

Since 2026-08-01 the stages are generic and driven by one registry entry (`src/ai_trade/strategy_registry.py`). You write **the spec** and **two modules**; the pipeline does the rest.

| Task | What you write |
| --- | --- |
| New instrument on an existing version | one cache entry in the version's `VersionSpec` |
| New version | rules module + audit-rules module + one `VersionSpec` |
| New strategy | the above + one `StrategySpec`; start with `python -m ai_trade.new_strategy --id strategy_05 --title "..."` |

Generic stages, none of which need a version-named copy: `run_strategy_version`, `sweep_version_parameter`, `summarize_version_ablation`, `verify_version`, and `ablation_grid`, which runs the whole gated grid in one command.

**An agent may write the rules module from the spec. It must not also write the audit.** The audit's only value is that it re-derives each rule from recorded columns *independently* — see `src/ai_trade/audit_rules_v1_2.py`, which imports nothing but `math` and `typing` and is held to that by an AST test. One author writing both means a misread spec passes its own check, and the parity gate cannot see the difference. Different author, spec only, no sight of the implementation.

## Phases and gates

**1. Spec before code.** Write `strategies/strategy_XX/vY/strategy.md` first: hypothesis with motivating evidence, exact rules, required ablation table, research warnings naming every in-sample parameter, promotion criteria. Exemplar: `strategies/strategy_04/v1_2/strategy.md`.

**2. Rules as hooks, never a copied loop.** A version supplies a `reaction_filter` and `extra_columns` to `strategy_04_causal_loop.signals_from_zone_events`. Variants are parameter configurations in the registry, never copies of the loop — copies drift, and the RRMS cost-duplication bug cost a full rerun. A version needing a *different base match* needs a third hook in the shared loop; add it there, not by copying.

**3. Non-negotiable gates before reading any result:**
- **Incumbent parity:** if a version claims "base ≡ incumbent", `verify_version` must prove it byte-for-byte (signals minus the version's `audit_columns`, trades exactly) per symbol. Parity fails ⇒ the harness is wrong; stop; nothing else may be read. A symbol with no incumbent gets no parity proof, and `ablation_grid` says so out loud — that is an absent yardstick, not a passed check.
- **Auditable columns:** every rule's decision value is recorded in `candidate_signals.csv` at decision time and recomputed by the audit rules from evidence alone (causality included: reference timestamps ≤ decision time).
- **Thresholds are swept, never chosen by code.** Sensitivity tables per symbol; the report is evidence for a human.
- **Per-symbol evidence only.** A filter that helps one symbol is not adopted elsewhere (v1.2's Filter B: +$1,328 QQQ, −$1,638 SPY, and +$1,912 GLD — three different verdicts from one rule).
- **Refactors prove they changed nothing.** Any change to shared pipeline code must leave every committed run reproducing byte for byte: `python scripts/verify_v1_2_reproduction.py`. Normalise line endings before comparing — `.gitattributes` makes a re-checked-out result LF while a fresh one is CRLF.

**4. Landing on the dashboard.** Write the standard six files and publish; `ablation_grid`'s final `publish` stage does this for a whole grid, which is the step whose absence once left runs showing "No published audit". New instruments must reuse the committed baseline's exact config + indicator dispatch (`symbol_run_inputs`); config drift invalidates every comparison.

**5. Deep-dive UI (per strategy).** New version ⇒ version chip + spec entry (variant row if ablation); new strategy with its own deep-dive ⇒ it becomes the FIRST/default tab. Check `strategyDescriptions.ts` has a condition entry; `npx tsc --noEmit` clean.

**6. Research record.** Commit results + ablation/sweep artifacts with caveats written INTO the files; every report carries a warning naming unvalidated parameters; update auto-memory. Promotion always requires out-of-sample confirmation — in-sample tables approve nothing.

## Red flags — stop and re-read the exemplars

- "Base is close enough to the incumbent"
- A threshold picked because the backtest liked it
- A second copy of the signal loop or cost computation
- The same author (human or agent) wrote both a rule and the audit that checks it
- An audit module importing anything from `ai_trade`
- A generated skeleton that returns `[]` instead of raising — indistinguishable from a real negative result
- A hardcoded symbol list anywhere outside the registry
- Results published whose filters can't be re-verified from the CSV
- Adopting a filter on all symbols because it worked on one
