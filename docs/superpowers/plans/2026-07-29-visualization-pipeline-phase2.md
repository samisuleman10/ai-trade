# Visualization Pipeline (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every finished backtest — existing or future, any strategy — publishes a validated bundle that the dashboard discovers automatically, with no file edited by hand.

**Architecture:** A shared exporter writes a `visualization/` bundle beside each result directory, publishing `manifest.json` last so half-written bundles are invisible. A backfill command publishes bundles for the 49 result directories already on disk. A read-only catalog API serves any directory containing a valid manifest. The dashboard lists what the catalog returns.

**Tech Stack:** Python 3.9 stdlib only (`json`, `csv`, `hashlib`, `http.server`), pytest 8; React 19, TypeScript, Vite.

## Global Constraints

- Python target is 3.9. Every new module starts with `from __future__ import annotations`. No `match` statements. No new third-party dependencies — stdlib only.
- `schema_version` is `"1.0.0"`. JSON property names are `snake_case`. Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ`.
- Numeric reconciliation tolerance is `1e-6` absolute.
- Dataset paths in a manifest are relative to `visualization/` and must never contain absolute paths, drive letters, or `..`.
- `manifest.json` is written LAST and atomically. A directory without a valid manifest is not a bundle and must not appear in the catalog.
- **Minimum bar for visibility:** a run publishes only if it has BOTH a trade ledger and a performance summary. Everything else is optional and declared in `capabilities`.
- Existing result artifacts (`fixed_trades.csv`, `fixed_summary.json`, `backtest_report.json`, archives, locked baselines) are READ-ONLY. Never modify or delete them.
- The API is read-only, binds to localhost, and serves only paths allow-listed by a validated manifest.

## Established facts (verified, do not re-derive)

- All four strategies emit an identical `fixed_summary.json` schema: `average_r, ending_equity, exit_reasons, long_trades, losses, max_drawdown, net_pnl, profit_factor, short_trades, trade_count, win_rate, wins`.
- All four emit an identical `fixed_trades.csv` header: `decision_timestamp, entry_timestamp, exit_timestamp, side, rrms_tier, quantity, entry_price, stop_price, target_price, exit_price, exit_reason, gross_pnl, costs, net_pnl, result_r, equity_after`.
- 48 of 49 result directories contain `backtest_report.json` carrying `strategy_id`, `symbol`, `mode`, and `data`. Run identity is READ from there, never inferred from the directory path.
- The one directory without it is `strategies/strategy_02/v1_5/results/validation/out_of_sample`; it is skipped with a reported reason, not guessed at.
- Existing reusable helpers: `ai_trade.strategy_01.load_ohlcv_csv(Path)`, `ai_trade.strategy_04_audit`, `ai_trade.build_strategy_04_fixture`.

---

### Task 1: Contract models, validation and atomic publication

**Files:**
- Create: `src/ai_trade/visualization_contract.py`
- Test: `tests/test_visualization_contract.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `SCHEMA_VERSION: str`
  - `Dataset` dataclass: `dataset_id, kind, path, payload, record_count, first_timestamp, last_timestamp`
  - `build_trade_ledger(rows, variant, run_id) -> Dataset`
  - `build_performance(rows, summary, variant, starting_equity) -> Dataset`
  - `publish_bundle(result_dir, identity, datasets, capabilities, warnings) -> Path`
  - `ContractError`
  - `read_manifest(bundle_dir) -> dict`

Trade IDs are deterministic: `<run_id>:<variant>:<six-digit one-based ordinal>`.

`build_performance` derives the equity curve from each trade's recorded `equity_after`. This is reshaping recorded producer values, not recomputing strategy logic. It anchors an initial point at `starting_equity` using the first trade's `decision_timestamp`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_visualization_contract.py`:

```python
import json

import pytest

from ai_trade.visualization_contract import (
    ContractError,
    SCHEMA_VERSION,
    build_performance,
    build_trade_ledger,
    publish_bundle,
    read_manifest,
)


def _rows():
    return [
        {
            "decision_timestamp": "2021-06-21T18:15:00Z",
            "entry_timestamp": "2021-06-21T18:15:00Z",
            "exit_timestamp": "2021-06-22T14:15:00Z",
            "side": "short",
            "rrms_tier": "0",
            "quantity": "227",
            "entry_price": "420.66",
            "stop_price": "421.32",
            "target_price": "420.01",
            "exit_price": "421.36",
            "exit_reason": "stop",
            "gross_pnl": "-158.90",
            "costs": "2.27",
            "net_pnl": "-161.17",
            "result_r": "-1.079",
            "equity_after": "99838.83",
        },
        {
            "decision_timestamp": "2021-08-03T14:30:00Z",
            "entry_timestamp": "2021-08-03T14:30:00Z",
            "exit_timestamp": "2021-08-03T15:45:00Z",
            "side": "long",
            "rrms_tier": "1",
            "quantity": "177",
            "entry_price": "437.81",
            "stop_price": "435.84",
            "target_price": "439.78",
            "exit_price": "439.73",
            "exit_reason": "target",
            "gross_pnl": "340.49",
            "costs": "1.77",
            "net_pnl": "338.72",
            "result_r": "0.972",
            "equity_after": "100177.55",
        },
    ]


def _summary():
    return {
        "trade_count": 2,
        "wins": 1,
        "losses": 1,
        "win_rate": 0.5,
        "net_pnl": 177.55,
        "ending_equity": 100177.55,
        "profit_factor": 2.1,
        "average_r": -0.0535,
        "max_drawdown": 161.17,
        "long_trades": 1,
        "short_trades": 1,
        "exit_reasons": {"stop": 1, "target": 1},
    }


def _identity():
    return {
        "run_id": "demo_run",
        "strategy_id": "strategy_04",
        "strategy_version": "v1_1",
        "symbol": "SPY",
        "mode": "historical_backtest",
    }


def test_trade_ids_are_deterministic_and_ordinal():
    ledger = build_trade_ledger(_rows(), "fixed", "demo_run")
    ids = [trade["trade_id"] for trade in ledger.payload["trades"]]
    assert ids == ["demo_run:fixed:000001", "demo_run:fixed:000002"]


def test_trade_ledger_reports_record_count_and_bounds():
    ledger = build_trade_ledger(_rows(), "fixed", "demo_run")
    assert ledger.record_count == 2
    assert ledger.first_timestamp == "2021-06-21T18:15:00Z"
    assert ledger.last_timestamp == "2021-08-03T14:30:00Z"


def test_performance_anchors_starting_equity_then_follows_trades():
    perf = build_performance(_rows(), _summary(), "fixed", 100000.0)
    points = perf.payload["points"]
    assert points[0]["equity"] == 100000.0
    assert points[-1]["equity"] == 100177.55
    assert points[-1]["trade_id"] == "demo_run:fixed:000002" or points[-1]["trade_id"] is None


def test_performance_rejects_summary_disagreeing_with_ledger():
    bad = dict(_summary(), ending_equity=999999.0)
    with pytest.raises(ContractError):
        build_performance(_rows(), bad, "fixed", 100000.0)


def test_publish_writes_manifest_last_and_hashes_every_sidecar(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    bundle = publish_bundle(tmp_path, _identity(), datasets, {"sizing_variants": ["fixed"]}, [])
    manifest = read_manifest(bundle)
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["status"] == "complete"
    assert manifest["execution_authority"] == "none"
    assert len(manifest["datasets"]) == 2
    for descriptor in manifest["datasets"]:
        assert len(descriptor["sha256"]) == 64
        sidecar = bundle / descriptor["path"]
        assert sidecar.exists()


def test_publish_refuses_a_bundle_without_trades_and_performance(tmp_path):
    only_trades = [build_trade_ledger(_rows(), "fixed", "demo_run")]
    with pytest.raises(ContractError):
        publish_bundle(tmp_path, _identity(), only_trades, {}, [])


def test_publish_rejects_a_dataset_path_escaping_the_bundle(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    datasets[0].path = "../escape.json"
    with pytest.raises(ContractError):
        publish_bundle(tmp_path, _identity(), datasets, {}, [])


def test_republishing_replaces_the_previous_manifest(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    publish_bundle(tmp_path, _identity(), datasets, {}, [])
    bundle = publish_bundle(tmp_path, _identity(), datasets, {}, [])
    manifest = read_manifest(bundle)
    assert manifest["run"]["run_id"] == "demo_run"


def test_read_manifest_rejects_a_directory_with_no_manifest(tmp_path):
    with pytest.raises(ContractError):
        read_manifest(tmp_path / "visualization")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_trade.visualization_contract'`

- [ ] **Step 3: Write the implementation**

Create `src/ai_trade/visualization_contract.py`. It must provide exactly the interface listed above and satisfy every test. Required behaviour:

- `Dataset` is a mutable dataclass with fields `dataset_id, kind, path, payload, record_count, first_timestamp, last_timestamp`.
- `build_trade_ledger(rows, variant, run_id)` converts CSV string rows to typed JSON. Numeric fields become floats, `quantity` and `rrms_tier` become ints. Emits `dataset_id=f"trades_{variant}"`, `kind="trades"`, `path=f"data/trades-{variant}.json"`. Each trade carries `trade_id`, `status="closed"`, and the canonical fields. Bounds come from the first and last `decision_timestamp`.
- `build_performance(rows, summary, variant, starting_equity)` emits `dataset_id=f"performance_{variant}"`, `kind="performance"`, `path=f"data/performance-{variant}.json"`, payload `{"schema_version", "dataset_id", "kind", "variant", "summary", "points"}`. Points anchor at `starting_equity` on the first trade's `decision_timestamp`, then one point per trade at its `exit_timestamp` carrying `trade_id`, `equity`, `peak_equity`, `drawdown`, `drawdown_percent`. Raise `ContractError` when the final equity disagrees with `summary["ending_equity"]` beyond tolerance, or when `summary["trade_count"]` disagrees with the row count.
- `publish_bundle(result_dir, identity, datasets, capabilities, warnings)` creates `result_dir/visualization/`, writes every sidecar, computes SHA-256 per sidecar, then writes `manifest.json` LAST via a temporary file plus `os.replace` so it appears atomically. Returns the bundle directory. Raise `ContractError` if the datasets do not include both a `trades` kind and a `performance` kind, or if any dataset path is absolute, contains a drive letter, or contains `..`.
- The manifest carries `schema_version`, `bundle_id`, `mode`, `status="complete"`, `generated_at`, `run`, `instrument`, `execution_authority="none"`, `warnings`, `capabilities`, and `datasets` with `sha256`, `record_count`, `first_timestamp`, `last_timestamp` per entry.
- `read_manifest(bundle_dir)` loads and returns the manifest, raising `ContractError` when it is absent or unparseable.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q`
Expected: `9 passed`

- [ ] **Step 5: Run the whole suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass, count increased by 9.

- [ ] **Step 6: Commit**

```bash
git add src/ai_trade/visualization_contract.py tests/test_visualization_contract.py
git commit -m "feat: add visualization bundle contract with atomic publication"
```

---

### Task 2: Backfill command for existing results

**Files:**
- Create: `src/ai_trade/backfill_visualization_bundles.py`
- Test: `tests/test_backfill_visualization_bundles.py`

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces: `discover_results(roots) -> list[Path]`, `run_identity(result_dir) -> dict | None`, `backfill(roots, dry_run) -> dict` with counts `published`, `skipped`, and a `reasons` mapping.

- [ ] **Step 1: Write the failing test**

Create `tests/test_backfill_visualization_bundles.py`:

```python
import json
from pathlib import Path

from ai_trade.backfill_visualization_bundles import (
    backfill,
    discover_results,
    run_identity,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_result(directory: Path, with_report: bool = True) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "fixed_trades.csv").write_text(
        "decision_timestamp,entry_timestamp,exit_timestamp,side,rrms_tier,quantity,"
        "entry_price,stop_price,target_price,exit_price,exit_reason,gross_pnl,costs,"
        "net_pnl,result_r,equity_after\n"
        "2021-06-21T18:15:00Z,2021-06-21T18:15:00Z,2021-06-22T14:15:00Z,short,0,227,"
        "420.66,421.32,420.01,421.36,stop,-158.90,2.27,-161.17,-1.079,99838.83\n",
        encoding="utf-8",
    )
    (directory / "fixed_summary.json").write_text(
        json.dumps(
            {
                "trade_count": 1,
                "wins": 0,
                "losses": 1,
                "win_rate": 0.0,
                "net_pnl": -161.17,
                "ending_equity": 99838.83,
                "profit_factor": 0.0,
                "average_r": -1.079,
                "max_drawdown": 161.17,
                "long_trades": 0,
                "short_trades": 1,
                "exit_reasons": {"stop": 1},
            }
        ),
        encoding="utf-8",
    )
    if with_report:
        (directory / "backtest_report.json").write_text(
            json.dumps({"strategy_id": "strategy_09_demo", "symbol": "SPY", "mode": "historical_backtest_only"}),
            encoding="utf-8",
        )


def test_discovery_finds_directories_holding_both_required_files(tmp_path):
    _make_result(tmp_path / "good")
    (tmp_path / "empty").mkdir()
    assert discover_results([tmp_path]) == [tmp_path / "good"]


def test_identity_is_read_from_the_report_not_guessed_from_the_path(tmp_path):
    _make_result(tmp_path / "whatever_folder_name")
    identity = run_identity(tmp_path / "whatever_folder_name")
    assert identity["strategy_id"] == "strategy_09_demo"
    assert identity["symbol"] == "SPY"


def test_a_result_without_a_report_is_skipped_with_a_reason(tmp_path):
    _make_result(tmp_path / "no_report", with_report=False)
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 0
    assert report["skipped"] == 1
    assert "no_report" in str(report["reasons"])


def test_backfill_publishes_a_readable_bundle(tmp_path):
    _make_result(tmp_path / "good")
    report = backfill([tmp_path], dry_run=False)
    assert report["published"] == 1
    manifest = json.loads((tmp_path / "good" / "visualization" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run"]["strategy_id"] == "strategy_09_demo"
    assert manifest["status"] == "complete"


def test_dry_run_writes_nothing(tmp_path):
    _make_result(tmp_path / "good")
    report = backfill([tmp_path], dry_run=True)
    assert report["published"] == 1
    assert not (tmp_path / "good" / "visualization").exists()


def test_real_repository_results_are_discovered():
    found = discover_results([REPO_ROOT / "outputs", REPO_ROOT / "strategies"])
    assert len(found) >= 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_backfill_visualization_bundles.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/ai_trade/backfill_visualization_bundles.py`:

- `discover_results(roots)` walks each root and returns every directory containing BOTH `fixed_trades.csv` and `fixed_summary.json`, sorted, skipping any directory already named `visualization`.
- `run_identity(result_dir)` reads `backtest_report.json` and returns `run_id` (the directory name), `strategy_id`, `strategy_version`, `symbol`, and `mode`. `strategy_version` is taken from the report when present, otherwise from the nearest path segment matching `^v[0-9_]+$`, otherwise `"unknown"`. Returns `None` when the report is missing or lacks `strategy_id`.
- `mode` normalises `"historical_backtest_only"` to `"historical_backtest"`.
- `backfill(roots, dry_run)` discovers, builds datasets for the `fixed` variant and, when `rrms_trades.csv` and `rrms_summary.json` both exist, the `rrms` variant too. Declares `capabilities={"sizing_variants": [...]}`. Publishes unless `dry_run`. Returns `{"published": int, "skipped": int, "reasons": {path: reason}}`. A directory that raises `ContractError` is counted as skipped with the error text as its reason — never allow one bad directory to abort the run.
- `main()` provides `--root` (repeatable, defaults to `outputs` and `strategies`), `--dry-run`, and prints the counts plus every skip reason.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_backfill_visualization_bundles.py -q`
Expected: `6 passed`

- [ ] **Step 5: Dry-run against the real repository**

Run: `./.venv/Scripts/python.exe -m ai_trade.backfill_visualization_bundles --dry-run`
Expected: a published count near 49 and an explicit reason for every skip. Read the skip reasons. If a directory is skipped for a reason other than missing metadata or failing reconciliation, stop and report it — a silent skip is a hidden data problem, not a success.

- [ ] **Step 6: Publish for real**

Run: `./.venv/Scripts/python.exe -m ai_trade.backfill_visualization_bundles`
Expected: bundles written. Confirm existing artifacts are untouched:

Run: `git status --short | grep -v visualization | head`
Expected: no modifications to any pre-existing `fixed_trades.csv`, `fixed_summary.json`, or `backtest_report.json`.

- [ ] **Step 7: Commit**

```bash
git add src/ai_trade/backfill_visualization_bundles.py tests/test_backfill_visualization_bundles.py
git commit -m "feat: backfill visualization bundles for existing results"
```

Commit the generated bundles separately so the code change stays reviewable:

```bash
git add outputs strategies
git commit -m "chore: publish visualization bundles for existing backtest results"
```

---

### Task 3: Read-only catalog API

**Files:**
- Modify: `src/ai_trade/server.py`
- Test: `tests/test_server_catalog.py`

**Interfaces:**
- Consumes: `read_manifest` from Task 1, bundles from Task 2.
- Produces: `build_catalog(roots) -> list[dict]` and the HTTP routes below.

Existing endpoints in `server.py` stay exactly as they are — `dashboard/src/App.tsx` still uses them.

New routes:
- `GET /api/runs` — catalog entries, filterable by exact `mode`, `strategy_id`, `strategy_version`, `symbol`
- `GET /api/runs/{bundle_id}/manifest`
- `GET /api/runs/{bundle_id}/datasets/{dataset_id}`
- `GET /health` — `{"status", "valid_bundles", "invalid_bundles"}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_server_catalog.py`:

```python
import json
from pathlib import Path

import pytest

from ai_trade.server import build_catalog, resolve_dataset_path


def _bundle(tmp_path: Path, bundle_id: str, strategy: str, symbol: str) -> Path:
    directory = tmp_path / bundle_id / "visualization"
    (directory / "data").mkdir(parents=True)
    (directory / "data" / "trades-fixed.json").write_text('{"trades": []}', encoding="utf-8")
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "bundle_id": bundle_id,
                "mode": "historical_backtest",
                "status": "complete",
                "run": {"run_id": bundle_id, "strategy_id": strategy, "strategy_version": "v1"},
                "instrument": {"symbol": symbol},
                "datasets": [
                    {"dataset_id": "trades_fixed", "kind": "trades", "path": "data/trades-fixed.json"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return directory


def test_catalog_lists_only_directories_with_a_manifest(tmp_path):
    _bundle(tmp_path, "run_a", "strategy_04", "SPY")
    (tmp_path / "run_b" / "visualization" / "data").mkdir(parents=True)
    entries = build_catalog([tmp_path])
    assert [entry["bundle_id"] for entry in entries] == ["run_a"]


def test_catalog_filters_are_exact(tmp_path):
    _bundle(tmp_path, "run_a", "strategy_04", "SPY")
    _bundle(tmp_path, "run_b", "strategy_01", "QQQ")
    entries = build_catalog([tmp_path], filters={"strategy_id": "strategy_01"})
    assert [entry["bundle_id"] for entry in entries] == ["run_b"]
    assert build_catalog([tmp_path], filters={"strategy_id": "strategy_0"}) == []


def test_only_manifest_declared_datasets_resolve(tmp_path):
    bundle = _bundle(tmp_path, "run_a", "strategy_04", "SPY")
    assert resolve_dataset_path(bundle, "trades_fixed").name == "trades-fixed.json"
    with pytest.raises(KeyError):
        resolve_dataset_path(bundle, "performance_fixed")


def test_path_traversal_is_rejected(tmp_path):
    bundle = _bundle(tmp_path, "run_a", "strategy_04", "SPY")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["datasets"].append({"dataset_id": "evil", "kind": "trades", "path": "../../../etc/passwd"})
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_dataset_path(bundle, "evil")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_server_catalog.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_catalog'`

- [ ] **Step 3: Write the implementation**

Add to `src/ai_trade/server.py`, leaving existing handlers untouched:

- `build_catalog(roots, filters=None)` walks each root for `visualization/manifest.json`, parses each, skips unparseable ones, and returns entries with `bundle_id`, `run`, `instrument`, `mode`, `generated_at`, `capabilities`, `dataset_ids`, and the bundle directory. Filters compare with exact equality against `run.strategy_id`, `run.strategy_version`, `instrument.symbol`, and `mode`.
- `resolve_dataset_path(bundle_dir, dataset_id)` looks the id up in the manifest's declared datasets, raising `KeyError` when undeclared. Raise `ValueError` when the declared path is absolute, has a drive letter, contains `..`, or resolves outside `bundle_dir`.
- Route the four endpoints listed above. Return JSON errors with stable `code` fields. Keep the existing localhost default.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_server_catalog.py -q`
Expected: `4 passed`

- [ ] **Step 5: Verify against the real bundles**

Start the server in one shell:

```bash
./.venv/Scripts/python.exe -m ai_trade.server --port 8080
```

Then in another:

```bash
curl -s "http://127.0.0.1:8080/api/runs" | head -c 600
```

Expected: a JSON array including entries for several strategies. Also confirm filtering and traversal defence:

```bash
curl -s "http://127.0.0.1:8080/api/runs?strategy_id=strategy_04" | head -c 400
```

- [ ] **Step 6: Run the whole suite and commit**

Run: `./.venv/Scripts/python.exe -m pytest -q`

```bash
git add src/ai_trade/server.py tests/test_server_catalog.py
git commit -m "feat: serve validated visualization bundles from a read-only catalog"
```

---

### Task 4: Dashboard run catalog

**Files:**
- Create: `dashboard/src/catalog.ts`
- Create: `dashboard/src/components/RunCatalog.tsx`
- Modify: `dashboard/src/Strategy04Dashboard.tsx`

**Interfaces:**
- Consumes: the API from Task 3.
- Produces: `fetchRuns(filters) -> Promise<CatalogEntry[]>`, `fetchDataset(bundleId, datasetId)`, and `<RunCatalog onSelectRun />`.

The Strategy 04 audit view built in Phase 1 stays exactly as it is. This task adds a catalog panel listing every discovered run across all strategies, showing each run's important numbers from its performance dataset, so Strategies 01, 02 and 03 become visible.

- [ ] **Step 1: Write the API client**

Create `dashboard/src/catalog.ts` exporting:

```typescript
export interface CatalogEntry {
  bundle_id: string;
  run: { run_id: string; strategy_id: string; strategy_version: string };
  instrument: { symbol: string };
  mode: string;
  generated_at: string;
  capabilities: Record<string, unknown>;
  dataset_ids: string[];
}

const BASE = 'http://localhost:8080';

export async function fetchRuns(filters: Record<string, string> = {}): Promise<CatalogEntry[]> {
  const query = new URLSearchParams(filters).toString();
  const response = await fetch(`${BASE}/api/runs${query ? `?${query}` : ''}`);
  if (!response.ok) throw new Error(`catalog request failed: ${response.status}`);
  return response.json();
}

export async function fetchDataset<T>(bundleId: string, datasetId: string): Promise<T> {
  const response = await fetch(`${BASE}/api/runs/${encodeURIComponent(bundleId)}/datasets/${encodeURIComponent(datasetId)}`);
  if (!response.ok) throw new Error(`dataset request failed: ${response.status}`);
  return response.json();
}
```

- [ ] **Step 2: Build the catalog panel**

Create `dashboard/src/components/RunCatalog.tsx`. It must:

- Fetch runs on mount and show a clear loading state.
- Group rows by `strategy_id`, then `strategy_version`, then `symbol`.
- For each run, fetch `performance_fixed` and show trade count, net P&L, win rate, profit factor and max drawdown — the important numbers.
- Show `—` for any number a run does not provide. Never substitute zero.
- When the API is unreachable, show an explicit message naming the command to start it (`python -m ai_trade.server --port 8080`) rather than rendering an empty list that looks like "no results".
- Call `onSelectRun(entry)` when a row is clicked.

Use the existing `s4-panel` and `s4-eyebrow` classes to match the current dashboard.

- [ ] **Step 3: Add it as a dashboard tab**

In `dashboard/src/Strategy04Dashboard.tsx`, add an `'runs'` view to the `View` union and a tab labelled "All runs" that renders `<RunCatalog />`. Do not alter the existing performance, comparison, rules, or chart views.

- [ ] **Step 4: Build and lint**

Run: `cd dashboard && npm run build`
Run: `cd dashboard && npx oxlint src`
Expected: both clean.

- [ ] **Step 5: Verify end to end**

Start the API, then the dashboard, open the "All runs" tab, and confirm runs from strategies 01, 02, 03 and 04 all appear with their numbers. Confirm the unreachable-API message renders when the API is stopped.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/catalog.ts dashboard/src/components/RunCatalog.tsx dashboard/src/Strategy04Dashboard.tsx
git commit -m "feat: list every discovered strategy run in the dashboard"
```

---

### Task 5: Publish on every future backtest

**Files:**
- Create: `src/ai_trade/publish_run.py`
- Modify: `src/ai_trade/backtest_strategy_04_v1_1.py`
- Test: `tests/test_publish_run.py`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: `publish_result_directory(result_dir) -> Path | None`.

This closes the loop: after a backtest writes its artifacts, it publishes a bundle, and the run appears in the dashboard with no manual step.

- [ ] **Step 1: Write the failing test**

Create `tests/test_publish_run.py`:

```python
import json
from pathlib import Path

from ai_trade.publish_run import publish_result_directory

from tests.test_backfill_visualization_bundles import _make_result


def test_publishing_a_finished_result_directory_creates_a_bundle(tmp_path):
    _make_result(tmp_path / "run")
    bundle = publish_result_directory(tmp_path / "run")
    assert bundle is not None
    assert (bundle / "manifest.json").exists()


def test_publishing_returns_none_when_requirements_are_missing(tmp_path):
    (tmp_path / "bare").mkdir()
    assert publish_result_directory(tmp_path / "bare") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_publish_run.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/ai_trade/publish_run.py` with `publish_result_directory(result_dir)`, reusing the Task 2 helpers for a single directory. It returns the bundle path, or `None` when the directory does not meet the minimum bar. It must never raise into a caller: a publication failure is reported by returning `None` and printing a warning, so a failed export can never destroy a completed backtest's real output.

- [ ] **Step 4: Hook it into the Strategy 04 backtest**

In `src/ai_trade/backtest_strategy_04_v1_1.py`, after all existing artifacts are written and immediately before the function returns, call `publish_result_directory(output_dir)` and print the resulting path. Locate the write-out by content. Change nothing else.

- [ ] **Step 5: Verify the loop end to end**

Re-run the Strategy 04 backtest into a scratch output directory, then confirm the new run appears in the catalog:

```bash
curl -s "http://127.0.0.1:8080/api/runs" | grep -c bundle_id
```

Expected: the count increases by one versus before the run.

- [ ] **Step 6: Run the whole suite and commit**

Run: `./.venv/Scripts/python.exe -m pytest -q`

```bash
git add src/ai_trade/publish_run.py tests/test_publish_run.py src/ai_trade/backtest_strategy_04_v1_1.py
git commit -m "feat: publish a visualization bundle at the end of every Strategy 04 run"
```

---

## Completion criteria

- Every result directory meeting the minimum bar has a validated bundle.
- `GET /api/runs` lists runs from strategies 01, 02, 03 and 04.
- The dashboard's "All runs" tab shows each run's important numbers, with `—` where a value is genuinely absent.
- Re-running a backtest makes its run appear with no file edited by hand.
- No pre-existing result artifact was modified.
- `pytest -q` passes and `npm run build` succeeds.

## Deliberate non-goals

Strategies 01, 02 and 03 get numbers and trade ledgers only. Their candles, indicator overlays and per-strategy diagnostics are not exported here — that is per-strategy work, and the manifest's `capabilities` field is how each strategy later declares the extras it supports. Strategy 04's zone and audit datasets remain the reference example of that mechanism.
