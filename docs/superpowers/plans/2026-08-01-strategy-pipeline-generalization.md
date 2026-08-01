# Strategy Pipeline Generalization

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. Every task ends green or is reverted; no task lands on a red gate.

**Goal:** Adding a new strategy (05, 06, 07…) or a new version of an existing one should require writing the *spec* and the *rules module* — nothing else. Data caching, running the ablation grid, verification scaffolding, sweeps, ablation tables, publishing and the dashboard tab all become pipeline driven by one registry entry.

**Why this is possible at all:** every stage after "signals exist" already operates on a fixed evidence contract (`candidate_signals.csv`, `fixed_trades.csv`, `*_summary.json`, `backtest_report.json`). Those stages are generic in substance and version-named only by accident of how they were written.

**Why it stops short of "prose only":** a backtest executes rules, and prose is not executable. The rules module is irreducibly code. An AI agent may *write* it from the spec — that is the intended authoring path — but it remains code that must be independently audited.

---

## The safety property this plan must not break

`verify_strategy_04_v1_2.py` re-derives Filter A and Filter B **from recorded CSV columns**, never by calling strategy code. That independence is the entire value of the audit: it can catch a bug in the implementation because it does not share the implementation.

Two rules follow, and they bind every task below:

1. **The audit is never generated from, nor imports, the strategy module.** Generic *scaffolding* (causality checks, reference-bar checks, parity diffing, empty-input guards) is shared. The per-version predicate that says "a row claiming Filter A passed must satisfy Filter A" stays hand-written against the spec.
2. **When an agent authors the rules, a different agent authors the audit**, from the spec only, without sight of the implementation. Otherwise verification is circular — the same misreading passes its own check.

## The mechanical gate

`scripts/verify_v1_2_reproduction.py` re-runs all 32 committed Strategy 04 v1.2 runs and compares five evidence files per run byte for byte. Confirmed deterministic and passing before any refactor (~8s per run).

**Every task in Phase A must leave this gate passing.** "The refactor looks equivalent" is not evidence. Reproducing thirty-two committed runs exactly is.

## Global constraints

- Python 3.9 floor. `from __future__ import annotations` in every module, so PEP 604/585 forms are fine *in annotations only* — never at runtime.
- No new dependencies, Python or npm.
- Existing CLIs keep working. Version-named modules may become thin wrappers, but `python -m ai_trade.backtest_strategy_04_v1_2_asset --symbol SPY --variant ab` must keep behaving identically until Phase A5 retires it deliberately.
- Full suite green before each commit: `python -m pytest tests -q` (400 passing at plan time).
- Never stage `dashboard/src/ledgerAudit.ts` or anything under `data/`.
- Frontend gate: `npx tsc --noEmit` from `dashboard/`.

---

# Phase A — generalize within Strategy 04 (the provable part)

This phase is where the byte-exact gate exists, so it is the only place a large refactor can be *proven* harmless. Phase B is mostly mechanical once these seams hold.

### Task A1: Shared causal loop

**Problem:** `signals_from_zone_events_v1_2` (≈130 lines) is `signals_from_zone_events_v1_1` copied with a filter hook and three extra output columns. Each future version copies it again.

**Files:** create `src/ai_trade/strategy_04_causal_loop.py`; rewrite `strategy_04_v1_2.py` and `strategy_04_v1_1.py` signal builders as thin wrappers. Test: `tests/test_strategy_04_causal_loop.py`.

**Interface:**

```python
def signals_from_zone_events(
    fifteen_minute_bars, one_hour_bars, events, params,
    *,
    reaction_filter=None,   # (zone, ReactionContext) -> bool; runs INSIDE zone
                            # matching, before selection and before used-zone
                            # marking, so a rejected zone stays available
    extra_columns=None,     # (selected_zone, ReactionContext) -> dict
) -> list[dict]
```

`ReactionContext` carries `previous`, `bar`, `next_bar`, `decision_time`, `stop_buffer`, `latest_atr`, `latest_atr_timestamp`, `reference_open`, `reference_close`, and the computed `side`/`stop` for a given zone.

- [ ] Diff `strategy_04_v1_1.py` against `strategy_04_v1_2.py` first and enumerate every behavioural difference before writing code. The ATR timeline differs (v1.2 carries the source bar's open/close); the shared loop always carries them and v1.1 ignores them — confirm that changes no filtering, since the `value is not None and value > 0` predicate is unchanged.
- [ ] Write the shared loop; make both versions wrappers.
- [ ] `python -m pytest tests/test_strategy_04_v1_2.py tests/test_strategy_04_v1_1.py -v`
- [ ] **Gate:** `python scripts/verify_v1_2_reproduction.py` — 32/32 byte-identical.
- [ ] Full suite, then commit.

### Task A2: Version registry and generic runner

**Files:** create `src/ai_trade/strategy_registry.py`, `src/ai_trade/run_strategy_version.py`. Test: `tests/test_strategy_registry.py`.

**Interface:** `VersionSpec` declaring `version_id`, `strategy_id`, `signal_builder`, `params_type`, `variants` (name → parameter overrides), `audit_columns`, `sweep_parameter` + `sweep_grid`, `results_template`, `change_description`, `warning`, and the symbol→cache mapping. `VERSIONS: dict[str, VersionSpec]`.

CLI: `python -m ai_trade.run_strategy_version --version strategy_04_v1_2 --symbol SPY --variant ab`.

- [ ] Registry + runner, with `backtest_strategy_04_v1_2_asset` reduced to a wrapper that delegates (keeping `SUPPORTED_SYMBOLS` and `symbol_run_inputs` exported — the grid, sweep and reproduction script import them).
- [ ] **Gate:** reproduction script twice — once with the default runner, once with `--runner ai_trade.run_strategy_version` (extend the script's flag handling if the version argument needs threading).
- [ ] Full suite, then commit.

### Task A3: Generic sweep and generic ablation summary

**Files:** create `src/ai_trade/sweep_version_parameter.py`, `src/ai_trade/summarize_version_ablation.py`; existing `sweep_strategy_04_v1_2_risk_ratio.py` / `summarize_strategy_04_v1_2_ablation.py` become wrappers. Extend their existing tests.

Both are already ~60–75% generic. The version-specific inputs are exactly `sweep_parameter`, `sweep_grid`, `variants`, and the prose caveats — all of which A2 put in the registry. The threshold-consistency guard becomes "all variants of a symbol share the same value for `sweep_parameter`".

- [ ] Implement; keep `ABLATION.md` and `SWEEP.md` output byte-identical for v1.2 (diff the regenerated files against the committed ones — this is a second, cheap gate).
- [ ] Full suite, then commit.

### Task A4: Generic verifier shell with per-version audit rules

**Files:** create `src/ai_trade/verify_version.py` (generic) and `src/ai_trade/audit_rules_v1_2.py` (hand-written). `verify_strategy_04_v1_2.py` becomes a wrapper.

Generic: row iteration, causality check, reference-bar open/close check, parity diff with `audit_columns` stripped, empty-input guards, report writing, exit code.
Per-version, hand-written, importing **no** strategy module: `audit_row(row, enabled_filters, params) -> list[str]`.

- [ ] Implement. Re-read the safety property above before starting.
- [ ] Add a test asserting `audit_rules_v1_2` imports nothing from `strategy_04_v1_2` — the independence is a property worth enforcing mechanically, not just by convention.
- [ ] Re-run verification for all 32 runs; every one still passes, and the 5 parity checks still pass.
- [ ] Full suite, then commit.

### Task A5: Point the grid at the generic modules

**Files:** `src/ai_trade/ablation_grid.py`, `tests/test_ablation_grid.py`.

`GridSpec` currently names five modules as strings. It should derive them from the registry: a grid entry becomes `{version_id, symbols, incumbent_symbols, incumbent_template}` and nothing else.

- [ ] Implement; `--dry-run` plan stays 64 commands in the same gate order.
- [ ] **Gate:** reproduction script, full suite, then commit.

---

# Phase B — lift to any strategy

### Task B1: Strategy-level registry

**Files:** extend `src/ai_trade/strategy_registry.py`.

`StrategySpec` — `strategy_id` (`strategy_04`), `title`, `subtitle`, `versions: list[VersionSpec]`, `spec_document`, `deep_dive` display config. `STRATEGIES: dict[str, StrategySpec]`, with `VERSIONS` derived from it so there is one source of truth.

- [ ] Register strategies 01–04 as they exist today; assert every currently-published run's `strategy_id` resolves.
- [ ] Full suite, then commit.

### Task B2: Dashboard config from the registry

**Files:** `src/ai_trade/export_strategy_registry.py` (writes a JSON the frontend reads), `dashboard/src/deepdive/registry.ts`.

Task 3/4 of the previous plan already made the deep dive config-driven; this removes the hand-written config module by generating it.

- [ ] Export; `registry.ts` builds `DEEP_DIVES` from the generated JSON, newest strategy first.
- [ ] `npx tsc --noEmit` clean; Strategy 04's screen behaves exactly as today.
- [ ] Commit.

### Task B3: Scaffolding command

**Files:** `src/ai_trade/new_strategy.py`. `python -m ai_trade.new_strategy --id strategy_05 --title "..."` generates: the spec document skeleton, a rules-module skeleton with the causal-loop hooks stubbed, an audit-rules skeleton, a registry entry, and a results directory. It writes no logic — it writes the places logic goes.

- [ ] Implement; generated skeleton must import cleanly and fail loudly ("not implemented") rather than silently returning zero signals. A new strategy that quietly produces no trades looks like a valid negative result, which is the worst possible failure mode.
- [ ] Commit.

### Task B4: Document the authoring workflow

**Files:** `.claude/skills/strategy-research/SKILL.md` (extend), `README.md`.

Document the intended path end to end: human writes the spec → agent A writes the rules module from the spec → agent B writes the audit rules from the spec alone → `ablation_grid` runs the gated grid → human reads the parity proof and decides promotion. State plainly which steps are human gates and why the audit is authored separately.

- [ ] Commit.

---

## Completion checklist

- [ ] `scripts/verify_v1_2_reproduction.py` passes 32/32 after every Phase A task
- [ ] A new *version* = a rules module + an audit-rules module + one registry entry
- [ ] A new *strategy* = the above, plus `new_strategy` scaffolding; no new React component, no new CLI
- [ ] The audit still shares no code with the strategy it audits, enforced by a test
- [ ] The parity gate still stops the grid before any filtered variant
- [ ] Full Python suite green; `npx tsc --noEmit` clean
