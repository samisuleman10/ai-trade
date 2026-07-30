# Research Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the strategy-research lifecycle from "a person issues twelve ordered commands and hand-writes a React screen" to "one command runs the gated grid, and a new strategy earns its deep-dive tab from a config entry."

**Architecture:** Three seams. (1) A declarative grid registry plus one orchestrator that shells out to the existing per-stage CLIs in gate order, refusing to continue past a failed incumbent-parity check. (2) The catalog's per-version condition text falls back to the published run summary, so a new strategy is never blank. (3) The bespoke `Strategy04Dashboard` becomes a config-driven `StrategyDeepDive`, and `App.tsx` derives its tabs from a deep-dive registry — newest strategy leftmost and landing, matching the convention already documented in `App.tsx:12-19`.

**Tech Stack:** Python 3.9 (stdlib + existing ai_trade modules), pytest; React + TypeScript (Vite), `npx tsc --noEmit` as the frontend gate — this repo has no frontend test runner.

**Reference:** `.claude/skills/strategy-research/SKILL.md` is the workflow this automates; its phase-3 gates are what Task 1 must enforce mechanically.

## Global Constraints

- **Do not rename or repurpose `src/ai_trade/research_pipeline.py`.** It is the Strategy 01 profile runner (`--profile/--run-id/--archive`) and is unrelated; the new orchestrator is a new module.
- Orchestration shells out to the existing CLIs via `subprocess` with `check=True`, following `research_pipeline.py`'s established pattern. Each CLI stays independently usable; no backtest logic is reimplemented.
- **The parity gate is absolute:** when a grid declares an incumbent, base-variant parity runs before any other stage, and a non-zero exit stops the run with a non-zero exit code. No later stage may execute. (Skill phase 3; spec wording: "the harness is wrong and no other result may be read.")
- Data paths are never re-hardcoded: the orchestrator imports `symbol_run_inputs` from the runner module to resolve each symbol's one-hour cache.
- Defaults preserve behaviour everywhere. Existing curated catalog condition text wins over published text (fallback only); every existing dashboard screen renders unchanged for strategies 01–04.
- Python tests: `python -m pytest tests/<file>.py -v` from repo root (Windows). Full suite green before each commit (known flake: `tests/test_server_concurrency.py` under full-suite load — if it is the sole failure, re-run that file alone and note it).
- Frontend: `npx tsc --noEmit` from `dashboard/` must be clean.
- Never stage `dashboard/src/ledgerAudit.ts` or anything under `data/`. Commit after every green task.
- No new dependencies, Python or npm.

---

### Task 1: Gated ablation-grid orchestrator

**Files:**
- Create: `src/ai_trade/ablation_grid.py`
- Test: `tests/test_ablation_grid.py` (create)

**Interfaces:**
- Consumes: `symbol_run_inputs` from `ai_trade.backtest_strategy_04_v1_2_asset` (returns `(fifteen_path, one_hour_path, config, indicator_params, market)`); the four existing CLIs named in `GRIDS` below.
- Produces: `GridSpec` dataclass; `GRIDS: dict[str, GridSpec]`; `plan_commands(spec, stages) -> list[list[str]]`; `run_grid(spec, stages, root, dry_run) -> int`; CLI `python -m ai_trade.ablation_grid --grid strategy_04_v1_2 [--stages ...] [--dry-run]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ablation_grid.py
import sys

import pytest

from ai_trade.ablation_grid import GRIDS, STAGES, plan_commands, run_grid


def _joined(commands):
    return [" ".join(command) for command in commands]


def test_grid_registry_shape():
    spec = GRIDS["strategy_04_v1_2"]
    assert spec.variants == ("base", "a", "b", "ab")
    assert spec.symbols == ("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD")
    assert spec.incumbent_results_template is not None


def test_plan_orders_base_and_parity_before_filtered_variants():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    first_filtered = next(i for i, line in enumerate(text) if "--variant a" in line)
    last_base_run = max(
        i for i, line in enumerate(text)
        if "backtest_strategy_04_v1_2_asset" in line and "--variant base" in line
    )
    last_parity = max(i for i, line in enumerate(text) if "--v1-1" in line)
    assert last_base_run < first_filtered, "base runs must precede filtered variants"
    assert last_parity < first_filtered, "parity gate must precede filtered variants"


def test_plan_covers_every_symbol_and_variant_once():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    runs = [line for line in text if "backtest_strategy_04_v1_2_asset" in line]
    assert len(runs) == 20
    for symbol in spec.symbols:
        for variant in spec.variants:
            assert sum(
                1 for line in runs if f"--symbol {symbol} " in line + " " and f"--variant {variant}" in line
            ) == 1, f"{symbol}/{variant}"


def test_plan_passes_each_symbols_own_one_hour_cache_to_the_verifier():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    verifications = [line for line in text if "verify_strategy_04_v1_2" in line]
    assert len(verifications) == 20
    eurusd = [line for line in verifications if "eurusd" in line]
    assert eurusd and all("EURUSD" in line for line in eurusd)
    assert all("--one-hour" in line for line in verifications)


def test_stage_selection_limits_the_plan():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, ("sweep",)))
    assert len(text) == 1
    assert "sweep_strategy_04_v1_2_risk_ratio" in text[0]


def test_dry_run_executes_nothing(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        "ai_trade.ablation_grid.subprocess.run",
        lambda *args, **kwargs: calls.append(args),
    )
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES, dry_run=True) == 0
    assert calls == []
    assert "backtest_strategy_04_v1_2_asset" in capsys.readouterr().out


def test_parity_failure_stops_before_filtered_variants(monkeypatch):
    executed = []

    def fake_run(command, **kwargs):
        executed.append(" ".join(command))
        if "--v1-1" in command:
            raise __import__("subprocess").CalledProcessError(1, command)
        return None

    monkeypatch.setattr("ai_trade.ablation_grid.subprocess.run", fake_run)
    exit_code = run_grid(GRIDS["strategy_04_v1_2"], STAGES)
    assert exit_code != 0
    assert not any("--variant a" in line for line in executed), "gate leaked into filtered variants"
    assert not any("sweep_strategy_04_v1_2" in line for line in executed)


def test_successful_run_executes_every_stage(monkeypatch):
    executed = []
    monkeypatch.setattr(
        "ai_trade.ablation_grid.subprocess.run",
        lambda command, **kwargs: executed.append(" ".join(command)),
    )
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES) == 0
    assert sum(1 for line in executed if "backtest_strategy_04_v1_2_asset" in line) == 20
    assert any("sweep_strategy_04_v1_2_risk_ratio" in line for line in executed)
    assert any("summarize_strategy_04_v1_2_ablation" in line for line in executed)


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        plan_commands(GRIDS["strategy_04_v1_2"], ("nonsense",))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ablation_grid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_trade.ablation_grid'`

- [ ] **Step 3: Implement**

Create `src/ai_trade/ablation_grid.py`:

```python
"""Run a strategy version's full ablation grid in gate order, once.

The lifecycle in .claude/skills/strategy-research/SKILL.md is a fixed
sequence: run the base variant, prove it reproduces the incumbent, only then
run the filtered variants, verify each one's recorded evidence, sweep the
threshold, summarise. Doing that by hand for five symbols and four variants
is twenty commands plus twenty verifications in the right order, and the
order is the safety property -- reading a filtered result before parity is
proven is exactly what the spec forbids.

This module owns the order and nothing else. Every stage shells out to the
CLI that already implements it, so each remains independently runnable and
this file contains no backtest, verification, or reporting logic. Adding a
future strategy version means adding one ``GridSpec`` to ``GRIDS``.
"""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STAGES: tuple[str, ...] = ("base", "parity", "variants", "audit", "sweep", "summary")


@dataclass(frozen=True)
class GridSpec:
    """Everything needed to drive one strategy version's ablation grid."""

    grid_id: str
    runner_module: str
    verifier_module: str
    sweep_module: str
    summarizer_module: str
    inputs_module: str
    symbols: tuple[str, ...]
    variants: tuple[str, ...]
    results_root: str
    results_dir_template: str
    incumbent_results_template: str | None
    incumbent_flag: str

    @property
    def base_variant(self) -> str:
        return self.variants[0]

    @property
    def filtered_variants(self) -> tuple[str, ...]:
        return self.variants[1:]

    def results_dir(self, symbol: str, variant: str) -> str:
        return self.results_dir_template.format(symbol=symbol.lower(), variant=variant)

    def incumbent_dir(self, symbol: str) -> str | None:
        if self.incumbent_results_template is None:
            return None
        return self.incumbent_results_template.format(symbol=symbol.lower())

    def one_hour_path(self, symbol: str) -> str:
        """Resolve a symbol's one-hour cache from the runner's own mapping.

        Imported rather than duplicated: a second copy of these paths could
        drift from the runs themselves, which is the failure the parity gate
        exists to catch.
        """
        module = importlib.import_module(self.inputs_module)
        _, one_hour, _, _, _ = module.symbol_run_inputs(symbol)
        return str(one_hour)


GRIDS: dict[str, GridSpec] = {
    "strategy_04_v1_2": GridSpec(
        grid_id="strategy_04_v1_2",
        runner_module="ai_trade.backtest_strategy_04_v1_2_asset",
        verifier_module="ai_trade.verify_strategy_04_v1_2",
        sweep_module="ai_trade.sweep_strategy_04_v1_2_risk_ratio",
        summarizer_module="ai_trade.summarize_strategy_04_v1_2_ablation",
        inputs_module="ai_trade.backtest_strategy_04_v1_2_asset",
        symbols=("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD"),
        variants=("base", "a", "b", "ab"),
        results_root="strategies/strategy_04/v1_2/results",
        results_dir_template="strategies/strategy_04/v1_2/results/{symbol}_1h_15m_{variant}",
        incumbent_results_template="strategies/strategy_04/v1_1/results/{symbol}_1h_15m",
        incumbent_flag="--v1-1",
    ),
}


def _run_command(spec: GridSpec, symbol: str, variant: str) -> list[str]:
    return [
        sys.executable, "-m", spec.runner_module,
        "--symbol", symbol,
        "--variant", variant,
    ]


def _verify_command(spec: GridSpec, symbol: str, variant: str, *, parity: bool) -> list[str]:
    command = [
        sys.executable, "-m", spec.verifier_module,
        "--results", spec.results_dir(symbol, variant),
        "--one-hour", spec.one_hour_path(symbol),
        "--variant", variant,
    ]
    if parity:
        incumbent = spec.incumbent_dir(symbol)
        if incumbent is not None:
            command.extend((spec.incumbent_flag, incumbent))
    return command


def plan_commands(spec: GridSpec, stages: tuple[str, ...]) -> list[list[str]]:
    """Return the exact command sequence for the requested stages, in gate order."""
    unknown = [stage for stage in stages if stage not in STAGES]
    if unknown:
        raise ValueError(f"Unknown stage(s) {unknown}; valid stages are {list(STAGES)}")

    commands: list[list[str]] = []
    if "base" in stages:
        commands.extend(_run_command(spec, symbol, spec.base_variant) for symbol in spec.symbols)
    if "parity" in stages:
        commands.extend(
            _verify_command(spec, symbol, spec.base_variant, parity=True)
            for symbol in spec.symbols
        )
    if "variants" in stages:
        commands.extend(
            _run_command(spec, symbol, variant)
            for variant in spec.filtered_variants
            for symbol in spec.symbols
        )
    if "audit" in stages:
        commands.extend(
            _verify_command(spec, symbol, variant, parity=False)
            for variant in spec.filtered_variants
            for symbol in spec.symbols
        )
    if "sweep" in stages:
        commands.append([sys.executable, "-m", spec.sweep_module])
    if "summary" in stages:
        commands.append(
            [sys.executable, "-m", spec.summarizer_module, "--results-root", spec.results_root]
        )
    return commands


def run_grid(
    spec: GridSpec,
    stages: tuple[str, ...] = STAGES,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    """Execute the planned commands in order, stopping at the first failure.

    Because the plan is ordered base -> parity -> filtered variants, stopping
    at the first failure IS the parity gate: a failed base-parity check exits
    before any filtered variant runs.
    """
    commands = plan_commands(spec, stages)
    for number, command in enumerate(commands, start=1):
        printable = " ".join(command)
        print(f"[{number}/{len(commands)}] {printable}")
        if dry_run:
            continue
        try:
            subprocess.run(command, cwd=root, check=True)
        except subprocess.CalledProcessError as error:
            print(
                f"STOPPED at step {number}/{len(commands)} (exit {error.returncode}): {printable}\n"
                "No later stage ran. If this was the base-parity check, the harness is wrong "
                "and no other result from this grid may be read.",
                file=sys.stderr,
            )
            return error.returncode or 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a strategy version's ablation grid in gate order."
    )
    parser.add_argument("--grid", required=True, choices=tuple(sorted(GRIDS)))
    parser.add_argument(
        "--stages", nargs="+", choices=STAGES, default=list(STAGES),
        help="Subset of stages to run, for resuming a long grid. Order is always the gate order.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the command sequence only.")
    args = parser.parse_args()
    return run_grid(GRIDS[args.grid], tuple(args.stages), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ablation_grid.py -v`
Expected: 9 passed

- [ ] **Step 5: Prove the real plan matches what was executed by hand**

Run: `python -m ai_trade.ablation_grid --grid strategy_04_v1_2 --dry-run`
Expected: 42 numbered lines — 5 base runs, 5 parity verifications (each carrying `--v1-1`), 15 filtered runs, 15 audits, 1 sweep, 1 summary. Confirm the FX verifications reference the EURUSD/GBPUSD one-hour caches, and that no `--variant a` line appears before the last `--v1-1` line.

- [ ] **Step 6: Full suite, then commit**

Run: `python -m pytest tests -q`

```bash
git add src/ai_trade/ablation_grid.py tests/test_ablation_grid.py
git commit -m "Run the ablation grid from one gated command"
```

---

### Task 2: Catalog condition text falls back to published data

**Files:**
- Modify: `src/ai_trade/visualization_contract.py` (`build_run_summary`, from line 385)
- Modify: `dashboard/src/hooks/useRunCatalog.ts` (run-summary fetch already present; expose the condition)
- Modify: `dashboard/src/strategyDescriptions.ts` (`conditionsFor`)
- Modify: `dashboard/src/components/RunCatalog.tsx` (use the fallback)
- Test: `tests/test_visualization_contract.py` (extend)

**Interfaces:**
- Produces: `run_summary` payload gains `"condition": str | None`; `conditionsFor(strategyId, publishedCondition?) -> string | null`.

- [ ] **Step 1: Write the failing Python test**

Add to `tests/test_visualization_contract.py`:

```python
def test_run_summary_condition_comes_from_a_single_change_from_key():
    from ai_trade.visualization_contract import build_run_summary

    dataset = build_run_summary({
        "strategy_id": "strategy_04_v1_2_rejection_filters",
        "change_from_v1_1": "Two independently switchable rejection filters.",
    })
    assert dataset.payload["condition"] == "Two independently switchable rejection filters."


def test_run_summary_condition_is_none_when_absent_or_ambiguous():
    from ai_trade.visualization_contract import build_run_summary

    absent = build_run_summary({"strategy_id": "strategy_04_v1"})
    assert absent.payload["condition"] is None

    # Two change_from_* keys cannot be ordered without guessing which version
    # the run actually changed from, so the field stays empty rather than
    # publishing a possibly wrong provenance claim.
    ambiguous = build_run_summary({
        "strategy_id": "x",
        "change_from_v1": "one",
        "change_from_v1_1": "two",
    })
    assert ambiguous.payload["condition"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_visualization_contract.py -k condition -v`
Expected: FAIL — `KeyError: 'condition'`

- [ ] **Step 3: Implement the Python side**

In `src/ai_trade/visualization_contract.py`, add above `build_run_summary`:

```python
def _published_condition(report: Mapping[str, Any]) -> Any:
    """Return the run's own description of what it changed, if unambiguous.

    Runners record this as ``change_from_<incumbent>`` (``change_from_v1``,
    ``change_from_v1_1``, ...), so the key name varies by version. Exactly one
    such key is readable; zero or several stay ``None`` rather than guessing a
    provenance claim the report never made.
    """
    matches = [
        value for key, value in report.items()
        if key.startswith("change_from_") and isinstance(value, str) and value.strip()
    ]
    return matches[0] if len(matches) == 1 else None
```

and inside `build_run_summary`'s `payload` dict, alongside the other top-level fields:

```python
        "condition": _published_condition(report),
```

- [ ] **Step 4: Run the Python tests**

Run: `python -m pytest tests/test_visualization_contract.py -v`
Expected: all passed

- [ ] **Step 5: Thread it through the dashboard**

In `dashboard/src/strategyDescriptions.ts`, replace the body of `conditionsFor` (keeping its existing export name and the `STRATEGY_CONDITIONS` map untouched):

```ts
/**
 * Curated text wins; a run's own published `condition` is the fallback.
 *
 * The map is hand-written per strategy version, so a newly published version
 * used to render a blank cell until someone remembered to add it. Falling
 * back to what the run itself recorded means a new strategy is never blank,
 * while the existing curated wording is preserved exactly.
 */
export function conditionsFor(strategyId: string, publishedCondition?: string | null): string | null {
  return STRATEGY_CONDITIONS[strategyId] ?? publishedCondition ?? null;
}
```

In `dashboard/src/hooks/useRunCatalog.ts`: the `RUN_SUMMARY_DATASET_ID` fetch already runs for every entry (it currently stores only `cost_model`). Add `condition?: string | null` to its `RunSummaryDataset` interface, keep a `conditions: Record<string, string>` state map alongside `costModels`, populate it in the same `.then(...)` when `dataset.condition` is a non-empty string, and return `conditions` from the hook.

In `dashboard/src/components/RunCatalog.tsx`: at the existing `conditionsFor(...)` call site, pass the published fallback — `conditionsFor(entry.run.strategy_id, conditions[entry.bundle_id])` — destructuring `conditions` from the hook alongside the existing values.

- [ ] **Step 6: Republish so the new field exists in bundles, and verify**

Run: `python -m ai_trade.backfill_visualization_bundles --roots strategies` (check the module's real flag names with `--help` first; use whatever it accepts to republish all discovered result directories).
Then: `npx tsc --noEmit` from `dashboard/` — clean.
Then confirm one bundle carries the field:

```bash
python -c "import json;print(json.load(open('strategies/strategy_04/v1_2/results/spy_1h_15m_ab/visualization/data/run-summary.json'))['condition'])"
```
Expected: the v1.2 change text, not `None`.

- [ ] **Step 7: Full suite, then commit**

Run: `python -m pytest tests -q`

```bash
git add src/ai_trade/visualization_contract.py tests/test_visualization_contract.py dashboard/src strategies
git commit -m "Fall back to each run's published condition in the catalog"
```

---

### Task 3: Deep-dive registry drives the tab bar

**Files:**
- Create: `dashboard/src/deepdive/registry.ts`
- Modify: `dashboard/src/App.tsx` (`Section` type, `SECTIONS`, `LANDING_SECTION`, the render switch, `footerLabel`)

**Interfaces:**
- Produces: `DeepDiveEntry` (`{ id: string; label: string; familyId: string; footerLabel: string }`) and `DEEP_DIVES: DeepDiveEntry[]` (newest strategy first). Task 4 extends the entry with its render config.

- [ ] **Step 1: Create the registry**

Create `dashboard/src/deepdive/registry.ts`:

```ts
/**
 * Which strategies have a deep-dive screen, newest first.
 *
 * `App` builds its tab bar from this list and opens the first entry, so a new
 * strategy's screen becomes the landing screen by adding one entry here --
 * the convention this file replaces was a hand-edited `SECTIONS` array.
 * A strategy only belongs here once it has a view of its own; 01, 02 and 03
 * live in Compare and All runs instead.
 */
export interface DeepDiveEntry {
  /** Stable tab id, also the nav key. */
  id: string;
  /** Tab label. */
  label: string;
  /** Catalog strategy family, e.g. `strategy_04`. */
  familyId: string;
  /** Footer provenance line shown while this tab is open. */
  footerLabel: string;
}

export const DEEP_DIVES: DeepDiveEntry[] = [
  {
    id: 'strategy04',
    label: 'Strategy 04',
    familyId: 'strategy_04',
    footerLabel: 'strategy_04 deep dive',
  },
];
```

- [ ] **Step 2: Drive App.tsx from it**

In `dashboard/src/App.tsx`:

- Import `DEEP_DIVES` from `./deepdive/registry`.
- Replace the `Section` type with `type Section = string` and build the nav list as: every `DEEP_DIVES` entry (mapped to `{ id, label, icon: Layers3 }`), then the existing `compare` and `runs` entries in that order. Keep the explanatory comment at `App.tsx:12-19`, updated to say the ordering now comes from the registry.
- `LANDING_SECTION` stays `SECTIONS[0].id` (unchanged semantics: first entry opens).
- Replace `{section === 'strategy04' && <Strategy04Dashboard />}` with a lookup: render `<Strategy04Dashboard />` when `section` matches a `DEEP_DIVES` entry id. (Task 4 replaces this with the config-driven component; keep the change mechanical here.)
- `footerLabel`: when the section is a deep-dive entry, use that entry's `footerLabel`; keep the `compare`/`runs` strings unchanged.

- [ ] **Step 3: Verify**

Run: `npx tsc --noEmit` from `dashboard/` — clean.
Then with the dev server running (`.claude/launch.json` config `dashboard`, port 5173), confirm the tab bar still reads **Strategy 04 · Compare strategies · All runs**, Strategy 04 is still the landing screen, and switching tabs still works. Evidence: page text showing the three tabs and the S4 header.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/deepdive/registry.ts dashboard/src/App.tsx
git commit -m "Build the tab bar from a deep-dive registry"
```

---

### Task 4: Config-driven deep-dive shell

**Files:**
- Create: `dashboard/src/deepdive/strategy04Config.ts`
- Rename/replace: `dashboard/src/Strategy04Dashboard.tsx` → `dashboard/src/deepdive/StrategyDeepDive.tsx`
- Modify: `dashboard/src/deepdive/registry.ts` (entry carries its config)
- Modify: `dashboard/src/App.tsx` (render `<StrategyDeepDive config={...} />`)
- Modify: `dashboard/src/strategy04Summary.ts`, `dashboard/src/strategy04Audit.ts` (family id + label sets from config, not hardcoded)

**Interfaces:**
- Consumes: `DEEP_DIVES` (Task 3).
- Produces: `DeepDiveConfig` — `{ familyId: string; title: string; subtitle: string; versions: Array<{id: string; label: string; description: string}>; variantsByVersion: Record<string, Array<{id: string; label: string; description: string}>>; assets: string[]; specs: Record<string, Strategy04Spec> }` — and `DEEP_DIVES[n].config`.

- [ ] **Step 1: Extract strategy 04's config**

Create `dashboard/src/deepdive/strategy04Config.ts` exporting a `DeepDiveConfig` built from what already exists in `strategy04Data.ts`: `familyId: 'strategy_04'`, title `'Strategy 04'`, subtitle `'Causal 1H zones · 15M reaction entries'`, `versions: STRATEGY_04_VERSIONS`, `variantsByVersion: { v1_2: STRATEGY_04_VARIANTS }`, `assets: STRATEGY_04_ASSETS`, `specs: STRATEGY_04_SPECS`. Re-export the `DeepDiveConfig` interface from this module's own file or from `registry.ts` — one home, imported by both. Do not duplicate the version/spec content; import it.

- [ ] **Step 2: Make the component take a config**

Move `Strategy04Dashboard.tsx` to `dashboard/src/deepdive/StrategyDeepDive.tsx` (`git mv`, so history follows) and change its default export to accept `{ config }: { config: DeepDiveConfig }`. Replace each hardcoded reference with the config equivalent:

- the `STRATEGY_04_VERSIONS` / `STRATEGY_04_VARIANTS` / `STRATEGY_04_ASSETS` / `STRATEGY_04_SPECS` imports become `config.versions` / `config.variantsByVersion[version] ?? []` / `config.assets` / `config.specs[version]`;
- the header title/subtitle come from `config.title` / `config.subtitle`;
- the initial `useState` values become `config.versions[0].id`, `config.assets[0]`, and `'base'` (or the first entry of that version's variant list when present);
- the variant chip row renders when `config.variantsByVersion[version]` is non-empty, replacing the `version === 'v1_2'` check;
- keep every existing state name, view tab, panel, and CSS class as-is — this task changes where values come from, not what renders.

Types: keep the per-strategy literal unions in `strategy04Data.ts` for that strategy's own modules, and let the shared component work with `string` ids. Where a hook signature currently demands `Strategy04Version`/`Strategy04Asset`/`Strategy04Variant`, widen it to `string` in `strategy04Summary.ts` and `strategy04Audit.ts` and pass `config.familyId` in place of the hardcoded `'strategy_04'` family check.

- [ ] **Step 3: Wire the registry and App**

In `registry.ts`, add `config: DeepDiveConfig` to `DeepDiveEntry` and set it on the strategy-04 entry (importing `strategy04Config`). In `App.tsx`, render `<StrategyDeepDive config={entry.config} />` for the matched deep-dive entry.

- [ ] **Step 4: Verify nothing regressed**

Run: `npx tsc --noEmit` from `dashboard/` — clean.
With the dev server running, walk the screen and confirm parity with today's behaviour:
1. Landing tab is Strategy 04; VERSION chips read v1.2 / v1.1 / v1.0.
2. Selecting **v1.2** reveals the VARIANT row (Base / Filter A / Filter B / A + B); selecting v1.1 or v1.0 hides it.
3. **v1.2 + Base + SPY** shows 38 trades / +$1,244.92 / 63.2% (the v1.1 parity property).
4. **v1.2 + Filter B + QQQ** shows 35 trades / 65.7% / +0.285R.
5. ASSET chips include EURUSD and GBPUSD; **v1.0 + EURUSD** shows the "no published run" notice rather than a spinner.
6. Compare assets, Rules, and Chart & trades tabs all still render.

Capture the page text for at least items 1–4 as evidence.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "Render the deep dive from a per-strategy config"
```

---

## Completion checklist

- [ ] `python -m ai_trade.ablation_grid --grid strategy_04_v1_2` runs the whole gated grid; a parity failure stops it before any filtered variant
- [ ] Adding a future version = one `GridSpec` entry, not twelve hand-ordered commands
- [ ] A newly published strategy version's condition text is never blank in All runs
- [ ] Tab bar and landing screen derive from `DEEP_DIVES`, newest strategy first
- [ ] A new strategy's deep-dive = one config module + one registry entry; no new component
- [ ] Strategy 04's screen behaves exactly as it does today (items 1–6 above verified)
- [ ] Full Python suite green; `npx tsc --noEmit` clean
