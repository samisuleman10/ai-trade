# Strategy 04 Audit Datasets — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the Strategy 04 audit as contract datasets so the deep-dive reads the API like every other screen, and the committed JSON fixtures can be deleted.

**Architecture:** `visualization_contract.py` gains three dataset builders — `zones`, `trade_audit`, and per-trade `candles` windows. A Strategy 04 publisher writes them into the same bundle that already carries `trades_fixed` and `performance_fixed`. The dashboard fetches `trades_fixed` plus the audit datasets and joins them on `trade_id` into the existing `AuditedTrade` shape, so `AuditedTradeList`, `TradeSetupChart`, and `TradeExecutionChart` are untouched.

**Tech Stack:** Python 3.9+, pytest 8; React 19, TypeScript, Vite, lightweight-charts 5.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md` §7 Phase 2.
- Contract: `docs/design/strategy_visualization/shared/architecture_and_data_contract.md`.
- Numeric tolerance `1e-6`; timestamps UTC `YYYY-MM-DDTHH:MM:SSZ`; JSON keys `snake_case`.
- Existing CSV/JSON research artifacts are never modified. Bundles are additive.
- The dashboard never recomputes indicators, zones, or outcomes.
- Every new Python module starts with `from __future__ import annotations`.
- Python 3.9: no `match`, no runtime `X | Y` unions.
- Repo files are LF. Never write Python source with text-mode `open()` on Windows — it emits CRLF and turns a 4-line edit into a whole-file diff.

## Design decisions

**Two datasets, not one.** The trade list needs only checks and zone geometry (~60 KB); the charts need bar windows (~1–2 MB). Splitting them lets the list render as soon as the small dataset lands instead of waiting on bars.

**Bar windows, not full series.** A contract `candles` series for SPY 15m is 34,200 bars (~2.2 MB) and the audit view only ever shows ~40 bars per trade. Windows are published under `kind: "candles"` with a `trade_id` on each window. A full-series `candles` dataset is what a general price chart would need; that is not this view and is not built here.

**No trade fields are republished.** `entry_price`, `stop_price`, `target_price`, `exit_price`, `exit_reason`, `result_r`, `side`, and the timestamps already exist in `trades_fixed`. The audit datasets carry only `trade_id`, `trigger_timestamp`, checks, zones, and bars. Duplicating them would create a second source of truth inside one bundle.

**Extend `backfill_visualization_bundles.py`, do not add a second publisher.** Backfill already discovers every result directory, derives identity from `backtest_report.json`, and computes the catalog-unique `bundle_id` via `bundle_id_for`. A separate Strategy 04 publisher would have to re-derive both, and a `bundle_id` that differed by one character would orphan the run from the catalog. The audit builder is a pure function backfill calls when a result directory qualifies.

**The join key is already fixed by the ledger.** `build_trade_ledger` assigns `f"{run_id}:{variant}:{ordinal:06d}"` with `run_id = result_dir.name`. The audit datasets must construct trade ids identically, in ledger order — Task 3's test asserts this rather than trusting it.

## Known limitation

The spec's §7 Phase 2 step 3 says the Strategy 04 backtest publishes its bundle as part of the run. This plan stops short of that: bundles are published by running `backfill_visualization_bundles`, so a rerun still needs one command afterwards. Hooking publication into each backtest entry point touches twelve CLIs and is its own change. What this plan does deliver is that the *dashboard* never needs editing again — which is the part that was duplicated work.

---

### Task 1: Zone and audit dataset builders

**Files:**
- Modify: `src/ai_trade/visualization_contract.py`
- Test: `tests/test_visualization_contract.py`

**Interfaces:**
- Consumes: existing `Dataset`, `ContractError`, `_trade_id` from `visualization_contract.py`.
- Produces: `build_zones(entries) -> Dataset` and `build_trade_audit(entries) -> Dataset`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_visualization_contract.py`:

```python
def _audit_entry(trade_id="run:fixed:000001", passed=True):
    return {
        "trade_id": trade_id,
        "trigger_timestamp": "2021-08-03T14:15:00Z",
        "checks": [
            {"check_id": "causality_atr", "passed": passed, "expected": "before", "actual": "ok"},
        ],
    }


def _zone_entry(trade_id="run:fixed:000001"):
    return {
        "trade_id": trade_id,
        "selected": {
            "zone_id": 39,
            "side": "demand",
            "lower": 437.0,
            "upper": 437.9,
            "qualified_timestamp": "2021-08-03T13:00:00Z",
            "score": 2,
        },
        "competing": [],
    }


def test_build_trade_audit_reports_pass_and_fail_counts():
    dataset = build_trade_audit([_audit_entry(), _audit_entry("run:fixed:000002", passed=False)])
    assert dataset.kind == "trade_audit"
    assert dataset.dataset_id == "trade_audit"
    assert dataset.record_count == 2
    assert dataset.payload["summary"] == {"audit_passed": 1, "audit_failed": 1}


def test_build_trade_audit_derives_passed_from_its_own_checks():
    """A stored `passed` flag that disagreed with the checks would misreport the audit."""

    dataset = build_trade_audit([_audit_entry(passed=False)])
    assert dataset.payload["trades"][0]["passed"] is False


def test_build_trade_audit_rejects_a_trade_with_no_checks():
    with pytest.raises(ContractError):
        build_trade_audit([{"trade_id": "run:fixed:000001", "trigger_timestamp": "x", "checks": []}])


def test_build_trade_audit_rejects_duplicate_trade_ids():
    with pytest.raises(ContractError):
        build_trade_audit([_audit_entry(), _audit_entry()])


def test_build_zones_requires_a_selected_zone():
    with pytest.raises(ContractError):
        build_zones([{"trade_id": "run:fixed:000001", "competing": []}])


def test_build_zones_keeps_competing_zones():
    dataset = build_zones([_zone_entry()])
    assert dataset.kind == "zones"
    assert dataset.record_count == 1
    assert dataset.payload["trades"][0]["selected"]["zone_id"] == 39
    assert dataset.payload["trades"][0]["competing"] == []


def test_build_zones_rejects_an_inverted_zone():
    """upper below lower is a geometry bug, not a renderable zone."""

    entry = _zone_entry()
    entry["selected"]["upper"] = 400.0
    with pytest.raises(ContractError):
        build_zones([entry])
```

Add `build_trade_audit` and `build_zones` to the module's existing import line in that test file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_trade_audit'`

- [ ] **Step 3: Write the implementation**

Add to `src/ai_trade/visualization_contract.py`, after `build_performance`:

```python
def build_zones(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """One-hour zone geometry per trade, including the zones it outranked.

    Competing zones are part of the contract, not decoration: the strategy
    ranks overlapping zones by evidence score, and a view that drew only the
    winner could never show that the ranking picked correctly.
    """

    seen: set = set()
    trades: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        if trade_id in seen:
            raise ContractError(f"duplicate trade_id in zones dataset: {trade_id!r}")
        seen.add(trade_id)

        selected = entry.get("selected")
        if not isinstance(selected, Mapping):
            raise ContractError(f"trade {trade_id}: zones entry has no 'selected' zone")

        competing = entry.get("competing") or []
        trades.append(
            {
                "trade_id": trade_id,
                "selected": _zone_payload(selected, trade_id),
                "competing": [_zone_payload(zone, trade_id) for zone in competing],
            }
        )

    return Dataset(
        dataset_id="zones",
        kind="zones",
        path="data/zones.json",
        payload={"schema_version": SCHEMA_VERSION, "dataset_id": "zones", "kind": "zones", "trades": trades},
        record_count=len(trades),
        first_timestamp=None,
        last_timestamp=None,
    )


def _zone_payload(zone: Mapping[str, Any], trade_id: str) -> Dict[str, Any]:
    lower = float(zone["lower"])
    upper = float(zone["upper"])
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ContractError(f"trade {trade_id}: zone bounds must be finite")
    if upper < lower:
        raise ContractError(f"trade {trade_id}: zone upper {upper} is below lower {lower}")
    return {
        "zone_id": int(zone["zone_id"]),
        "side": str(zone["side"]),
        "lower": lower,
        "upper": upper,
        "qualified_timestamp": str(zone.get("qualified_timestamp") or ""),
        "score": int(zone.get("score") or 0),
    }


def build_trade_audit(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """Per-trade rule-check results.

    ``passed`` is derived here from the checks rather than copied from the
    producer, so a summary can never disagree with the evidence beneath it.
    """

    seen: set = set()
    trades: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        if trade_id in seen:
            raise ContractError(f"duplicate trade_id in trade_audit dataset: {trade_id!r}")
        seen.add(trade_id)

        checks = list(entry.get("checks") or [])
        if not checks:
            raise ContractError(f"trade {trade_id}: audit entry has no checks")

        normalized = []
        for check in checks:
            normalized.append(
                {
                    "check_id": str(check["check_id"]),
                    "passed": bool(check["passed"]),
                    "expected": str(check.get("expected", "")),
                    "actual": str(check.get("actual", "")),
                }
            )
        trades.append(
            {
                "trade_id": trade_id,
                "trigger_timestamp": str(entry.get("trigger_timestamp") or ""),
                "passed": all(check["passed"] for check in normalized),
                "checks": normalized,
            }
        )

    return Dataset(
        dataset_id="trade_audit",
        kind="trade_audit",
        path="data/trade-audit.json",
        payload={
            "schema_version": SCHEMA_VERSION,
            "dataset_id": "trade_audit",
            "kind": "trade_audit",
            "summary": {
                "audit_passed": sum(1 for trade in trades if trade["passed"]),
                "audit_failed": sum(1 for trade in trades if not trade["passed"]),
            },
            "trades": trades,
        },
        record_count=len(trades),
        first_timestamp=None,
        last_timestamp=None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q`
Expected: all pass, including the seven new tests.

- [ ] **Step 5: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: `228 passed`

- [ ] **Step 6: Commit**

```bash
git add src/ai_trade/visualization_contract.py tests/test_visualization_contract.py
git commit -m "Add zones and trade_audit dataset kinds to the contract"
```

---

### Task 2: Per-trade candle window dataset

**Files:**
- Modify: `src/ai_trade/visualization_contract.py`
- Test: `tests/test_visualization_contract.py`

**Interfaces:**
- Consumes: `Dataset`, `ContractError` from Task 1's module.
- Produces: `build_audit_windows(entries) -> Dataset`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_visualization_contract.py`:

```python
def _bar(timestamp, low=99.0, high=101.0):
    return {"timestamp": timestamp, "open": 100.0, "high": high, "low": low, "close": 100.5, "volume": 10.0}


def _window_entry(trade_id="run:fixed:000001"):
    return {
        "trade_id": trade_id,
        "one_hour": [_bar("2021-08-03T13:00:00Z"), _bar("2021-08-03T14:00:00Z")],
        "fifteen_minute": [_bar("2021-08-03T14:15:00Z")],
    }


def test_build_audit_windows_spans_every_bar_it_carries():
    dataset = build_audit_windows([_window_entry()])
    assert dataset.kind == "candles"
    assert dataset.dataset_id == "audit_windows"
    assert dataset.record_count == 1
    assert dataset.first_timestamp == "2021-08-03T13:00:00Z"
    assert dataset.last_timestamp == "2021-08-03T14:15:00Z"


def test_build_audit_windows_rejects_an_impossible_bar():
    """low above high is not a bar; rendering it would draw an inverted candle."""

    entry = _window_entry()
    entry["one_hour"][0]["low"] = 500.0
    with pytest.raises(ContractError):
        build_audit_windows([entry])


def test_build_audit_windows_rejects_unordered_bars():
    entry = _window_entry()
    entry["one_hour"] = [_bar("2021-08-03T14:00:00Z"), _bar("2021-08-03T13:00:00Z")]
    with pytest.raises(ContractError):
        build_audit_windows([entry])


def test_build_audit_windows_rejects_a_trade_with_no_bars():
    with pytest.raises(ContractError):
        build_audit_windows([{"trade_id": "run:fixed:000001", "one_hour": [], "fifteen_minute": []}])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q -k audit_windows`
Expected: FAIL with `NameError: name 'build_audit_windows' is not defined`

- [ ] **Step 3: Write the implementation**

Add to `src/ai_trade/visualization_contract.py`:

```python
def _validate_window(bars: Sequence[Mapping[str, Any]], trade_id: str, label: str) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    previous: Optional[str] = None
    for index, bar in enumerate(bars):
        timestamp = _row_str(bar, "timestamp", index)
        if previous is not None and timestamp <= previous:
            raise ContractError(
                f"trade {trade_id}: {label} bars are not strictly ascending at {timestamp!r}"
            )
        previous = timestamp
        values = {field: _row_float(bar, field, index) for field in ("open", "high", "low", "close")}
        if not values["low"] <= min(values["open"], values["close"]) or not max(
            values["open"], values["close"]
        ) <= values["high"]:
            raise ContractError(f"trade {trade_id}: {label} bar at {timestamp} violates low<=o,c<=high")
        normalized.append({"timestamp": timestamp, **values, "volume": _row_float(bar, "volume", index)})
    return normalized


def build_audit_windows(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """Bounded bar windows around each audited trade.

    Deliberately not a full candle series. The audit view shows roughly forty
    bars per trade, and a full 15-minute series for one symbol is over 34,000
    bars -- publishing it whole would ship two megabytes to render forty.
    """

    trades: List[Dict[str, Any]] = []
    stamps: List[str] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        one_hour = _validate_window(entry.get("one_hour") or [], trade_id, "one_hour")
        fifteen = _validate_window(entry.get("fifteen_minute") or [], trade_id, "fifteen_minute")
        if not one_hour and not fifteen:
            raise ContractError(f"trade {trade_id}: audit window carries no bars")
        trades.append({"trade_id": trade_id, "one_hour": one_hour, "fifteen_minute": fifteen})
        stamps.extend(bar["timestamp"] for bar in one_hour)
        stamps.extend(bar["timestamp"] for bar in fifteen)

    return Dataset(
        dataset_id="audit_windows",
        kind="candles",
        path="data/audit-windows.json",
        payload={
            "schema_version": SCHEMA_VERSION,
            "dataset_id": "audit_windows",
            "kind": "candles",
            "trades": trades,
        },
        record_count=len(trades),
        first_timestamp=min(stamps) if stamps else None,
        last_timestamp=max(stamps) if stamps else None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_visualization_contract.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/visualization_contract.py tests/test_visualization_contract.py
git commit -m "Publish bounded audit bar windows as a candles dataset"
```

---

### Task 3: Build the audit datasets and publish them via backfill

**Files:**
- Create: `src/ai_trade/strategy_04_audit_datasets.py`
- Modify: `src/ai_trade/backfill_visualization_bundles.py`
- Test: `tests/test_strategy_04_audit_datasets.py`

**Interfaces:**
- Consumes: `build_zones`, `build_trade_audit`, `build_audit_windows` (Tasks 1-2); `load_signals`, `load_trades`, `window`, `competing_zones`, `resolve_max_long_penetration`, and the four window-size constants from `build_strategy_04_fixture`; `audit_trade` from `strategy_04_audit`.
- Produces: `audit_datasets_for(result_dir, repo_root) -> List[Dataset]` returning `[]` when the directory is not an auditable Strategy 04 run.

Bar file paths come from `backtest_report.json`'s `data.one_hour_file` / `data.fifteen_minute_file`, which record exactly what the run consumed. Deriving them from the symbol would guess, and a v4 versus v5 cache would silently audit against different bars than the backtest used.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_strategy_04_audit_datasets.py`:

```python
from pathlib import Path

import pytest

from ai_trade.strategy_04_audit_datasets import audit_datasets_for, report_bar_paths

REPO_ROOT = Path(__file__).resolve().parent.parent
S4_RESULT = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"


def test_report_bar_paths_normalizes_recorded_windows_separators():
    """backtest_report.json records paths with backslashes on Windows."""

    paths = report_bar_paths({"data": {"one_hour_file": "data\\m\\spy_1h.csv", "fifteen_minute_file": "data\\m\\spy_15m.csv"}})
    assert paths == ("data/m/spy_1h.csv", "data/m/spy_15m.csv")


def test_report_bar_paths_returns_none_when_not_recorded():
    assert report_bar_paths({"data": {}}) is None
    assert report_bar_paths({}) is None


def test_a_non_strategy_04_directory_yields_no_audit_datasets(tmp_path):
    assert audit_datasets_for(tmp_path, REPO_ROOT) == []


def test_strategy_04_result_yields_the_three_datasets():
    datasets = audit_datasets_for(S4_RESULT, REPO_ROOT)
    assert [d.dataset_id for d in datasets] == ["zones", "trade_audit", "audit_windows"]
    assert [d.kind for d in datasets] == ["zones", "trade_audit", "candles"]


def test_audit_trade_ids_match_the_ledger_ids_in_order():
    """The dashboard joins on trade_id; a mismatch renders an empty audit."""

    from ai_trade.backfill_visualization_bundles import _build_variant_datasets

    ledger = _build_variant_datasets(S4_RESULT, "fixed", S4_RESULT.name)[0]
    expected = [trade["trade_id"] for trade in ledger.payload["trades"]]
    for dataset in audit_datasets_for(S4_RESULT, REPO_ROOT):
        assert [t["trade_id"] for t in dataset.payload["trades"]] == expected, dataset.dataset_id


def test_every_trade_is_audited_not_just_the_ones_with_zones():
    datasets = {d.dataset_id: d for d in audit_datasets_for(S4_RESULT, REPO_ROOT)}
    counts = {name: dataset.record_count for name, dataset in datasets.items()}
    assert len(set(counts.values())) == 1, counts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_strategy_04_audit_datasets.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_trade.strategy_04_audit_datasets'`

- [ ] **Step 3: Write the implementation**

Create `src/ai_trade/strategy_04_audit_datasets.py`:

```python
"""Build Strategy 04's audit datasets for a published visualization bundle.

Phase 2 of docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md.
These are the datasets the dashboard's deep-dive reads instead of the
committed JSON fixtures it used to import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ai_trade.build_strategy_04_fixture import (
    FIFTEEN_MINUTE_BARS_AFTER,
    FIFTEEN_MINUTE_BARS_BEFORE,
    ONE_HOUR_BARS_AFTER,
    ONE_HOUR_BARS_BEFORE,
    competing_zones,
    load_signals,
    load_trades,
    resolve_max_long_penetration,
    window,
)
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_audit import audit_trade
from ai_trade.strategy_04_indicator import (
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.visualization_contract import (
    ContractError,
    Dataset,
    build_audit_windows,
    build_trade_audit,
    build_zones,
)

REPORT_FILENAME = "backtest_report.json"
SIGNALS_FILENAME = "candidate_signals.csv"


def report_bar_paths(report: Any) -> Optional[Tuple[str, str]]:
    """Return the (one_hour, fifteen_minute) bar paths the run recorded.

    Paths are stored as written on the producing machine, so Windows
    separators are normalized. Returns ``None`` when either is absent --
    an audit must never guess which bars a run consumed.
    """

    if not isinstance(report, dict):
        return None
    data = report.get("data")
    if not isinstance(data, dict):
        return None
    one_hour = data.get("one_hour_file")
    fifteen = data.get("fifteen_minute_file")
    if not one_hour or not fifteen:
        return None
    return str(one_hour).replace("\\", "/"), str(fifteen).replace("\\", "/")


def _bar_json(bar: Any) -> Dict[str, Any]:
    return {
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _zone_json(zone: Any, lower: float, upper: float, side: str) -> Dict[str, Any]:
    return {
        "zone_id": zone.zone_id,
        "side": side,
        "lower": lower,
        "upper": upper,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "score": zone.qualification_score,
    }


def _is_auditable(result_dir: Path) -> Optional[Dict[str, Any]]:
    report_path = result_dir / REPORT_FILENAME
    if not report_path.is_file() or not (result_dir / SIGNALS_FILENAME).is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not str(report.get("strategy_id", "")).startswith("strategy_04"):
        return None
    return report


def audit_datasets_for(result_dir: Any, repo_root: Any) -> List[Dataset]:
    """Zones, checks and bar windows for one Strategy 04 result directory.

    Returns ``[]`` for any directory that is not an auditable Strategy 04
    run, so ``backfill`` can call this unconditionally.
    """

    result_dir = Path(result_dir)
    repo_root = Path(repo_root)

    report = _is_auditable(result_dir)
    if report is None:
        return []
    bar_paths = report_bar_paths(report)
    if bar_paths is None:
        return []

    one_hour_path = repo_root / bar_paths[0]
    fifteen_minute_path = repo_root / bar_paths[1]
    if not one_hour_path.is_file() or not fifteen_minute_path.is_file():
        return []

    signals = {s.decision_timestamp: s for s in load_signals(result_dir / SIGNALS_FILENAME)}
    trades = load_trades(result_dir / "fixed_trades.csv")

    hour_bars = load_ohlcv_csv(one_hour_path)
    minute_bars = load_ohlcv_csv(fifteen_minute_path)
    minute_timestamps = [bar.timestamp for bar in minute_bars]
    indicator = build_one_hour_indicator(hour_bars, strategy_04_v0_3_parameters())
    zones_by_id = {zone.zone_id: zone for zone in indicator.zones}

    strategy_version = report.get("strategy_version") or _version_from_path(result_dir)
    cap = resolve_max_long_penetration(None, strategy_version)

    run_id = result_dir.name
    zone_entries: List[Dict[str, Any]] = []
    audit_entries: List[Dict[str, Any]] = []
    window_entries: List[Dict[str, Any]] = []

    for ordinal, trade in enumerate(trades, start=1):
        trade_id = "%s:fixed:%06d" % (run_id, ordinal)
        signal = signals.get(trade.decision_timestamp)
        if signal is None:
            raise ContractError(
                "trade %s has no candidate signal at %s" % (trade_id, trade.decision_timestamp)
            )
        selected = zones_by_id.get(signal.zone_id)
        if selected is None:
            raise ContractError(
                "zone %d referenced by %s is missing from the rebuilt timeline"
                % (signal.zone_id, trade.decision_timestamp)
            )

        checks = audit_trade(signal, trade, selected.qualified_timestamp or "", minute_timestamps, cap)
        audit_entries.append(
            {
                "trade_id": trade_id,
                "trigger_timestamp": signal.trigger_timestamp,
                "checks": [
                    {"check_id": c.check_id, "passed": c.passed, "expected": c.expected, "actual": c.actual}
                    for c in checks
                ],
            }
        )
        zone_entries.append(
            {
                "trade_id": trade_id,
                "selected": _zone_json(selected, signal.zone_lower, signal.zone_upper, signal.zone_side),
                "competing": [
                    _zone_json(
                        zone,
                        zone.qualified_lower if zone.qualified_lower is not None else zone.lower,
                        zone.qualified_upper if zone.qualified_upper is not None else zone.upper,
                        zone.origin_side,
                    )
                    for zone in competing_zones(indicator.zones, selected, signal)
                ],
            }
        )
        window_entries.append(
            {
                "trade_id": trade_id,
                "one_hour": [
                    _bar_json(bar)
                    for bar in window(
                        hour_bars,
                        selected.qualified_timestamp or trade.entry_timestamp,
                        trade.exit_timestamp,
                        ONE_HOUR_BARS_BEFORE,
                        ONE_HOUR_BARS_AFTER,
                    )
                ],
                "fifteen_minute": [
                    _bar_json(bar)
                    for bar in window(
                        minute_bars,
                        signal.trigger_timestamp,
                        trade.exit_timestamp,
                        FIFTEEN_MINUTE_BARS_BEFORE,
                        FIFTEEN_MINUTE_BARS_AFTER,
                    )
                ],
            }
        )

    return [
        build_zones(zone_entries),
        build_trade_audit(audit_entries),
        build_audit_windows(window_entries),
    ]


def _version_from_path(result_dir: Path) -> str:
    for part in reversed(result_dir.parts):
        if part.startswith("v") and all(ch.isdigit() or ch == "_" for ch in part[1:]):
            return part
    return "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_strategy_04_audit_datasets.py -q`
Expected: `6 passed`

- [ ] **Step 5: Call it from backfill**

In `src/ai_trade/backfill_visualization_bundles.py`, inside `backfill`'s per-directory `try`, immediately after the `rrms` block and before `publish_identity` is built, add:

```python
            audit_datasets = audit_datasets_for(result_dir, REPO_ROOT)
            datasets.extend(audit_datasets)
```

and add to the capabilities dict:

```python
            capabilities = {"sizing_variants": variants, "has_trade_audit": bool(audit_datasets)}
```

Import `audit_datasets_for` from `ai_trade.strategy_04_audit_datasets` at the top.

`capabilities.has_trade_audit` is what lets the dashboard hide the audit view for runs that do not publish one, rather than fetching a dataset that is not there.

- [ ] **Step 6: Republish every bundle**

Run: `./.venv/Scripts/python.exe -m ai_trade.backfill_visualization_bundles`
Expected: 48 published, 0 skipped. Any skip reason mentioning Strategy 04 is a failure — investigate rather than proceed.

Confirm the datasets landed:

Run: `./.venv/Scripts/python.exe -c "import json,glob;[print(p.split('visualization')[0][-28:],[d['dataset_id'] for d in json.load(open(p))['datasets']]) for p in sorted(glob.glob('strategies/strategy_04/**/visualization/manifest.json',recursive=True))]"`
Expected: all six list `zones`, `trade_audit` and `audit_windows` alongside the trades and performance datasets.

- [ ] **Step 7: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/ai_trade/strategy_04_audit_datasets.py src/ai_trade/backfill_visualization_bundles.py tests/test_strategy_04_audit_datasets.py strategies/ outputs/
git commit -m "Publish Strategy 04 zones, checks and bar windows in the bundle"
```

---

### Task 4: Dashboard reads the audit from the API

**Files:**
- Modify: `dashboard/src/strategy04Fixture.ts` (renamed to `dashboard/src/strategy04Audit.ts`)
- Modify: `dashboard/src/Strategy04Dashboard.tsx`

**Interfaces:**
- Consumes: `fetchDataset`, `fetchRuns` from `catalog.ts`; the datasets from Task 3.
- Produces: `useStrategy04Audit(version, asset) -> { status, trades }` returning the existing `AuditedTrade[]` shape.

The `AuditedTrade` interface, `toChartBars`, `toEpochSeconds`, and `failedChecks` all stay exactly as they are. `AuditedTradeList`, `TradeSetupChart`, and `TradeExecutionChart` are not modified in this task — if they need changing, the join is wrong.

- [ ] **Step 1: Replace the fixture loader with an API loader**

Rename the exported types as part of this move: `FixtureZone` becomes `AuditZone`, `FixtureBar` becomes `AuditBar`, and `Strategy04Fixture` is deleted (nothing consumes the whole document any more). `AuditedTrade`, `AuditCheck`, `AuditResult`, `toChartBars`, `toEpochSeconds`, and `failedChecks` keep their names and shapes so the chart components are untouched.

Delete `FIXTURE_LOADERS`, `hasStrategy04Fixture`, `loadStrategy04Fixture`, and `useStrategy04Fixture`. Add:

```typescript
import { fetchDataset, fetchRuns } from './catalog';

interface AuditDataset {
  trades: Array<{ trade_id: string; trigger_timestamp: string; passed: boolean; checks: AuditCheck[] }>;
}
interface ZonesDataset {
  trades: Array<{ trade_id: string; selected: AuditZone; competing: AuditZone[] }>;
}
interface WindowsDataset {
  trades: Array<{ trade_id: string; one_hour: AuditBar[]; fifteen_minute: AuditBar[] }>;
}
interface LedgerDataset {
  trades: Array<Record<string, unknown>>;
}

const byTradeId = <T extends { trade_id: string }>(rows: T[]): Map<string, T> =>
  new Map(rows.map((row) => [row.trade_id, row]));

/**
 * Join the run's trade ledger to its audit datasets.
 *
 * The ledger is the single source for prices, sides and outcomes; the audit
 * datasets add only checks, zones and bars. A trade the audit does not cover
 * is dropped rather than rendered with blank checks, because a trade shown
 * with no failures must mean it was checked and passed.
 */
export function assembleAuditedTrades(
  ledger: LedgerDataset,
  audit: AuditDataset,
  zones: ZonesDataset,
  windows: WindowsDataset,
): AuditedTrade[] {
  const auditById = byTradeId(audit.trades);
  const zonesById = byTradeId(zones.trades);
  const windowsById = byTradeId(windows.trades);

  const assembled: AuditedTrade[] = [];
  ledger.trades.forEach((row, index) => {
    const tradeId = String(row.trade_id);
    const auditRow = auditById.get(tradeId);
    const zoneRow = zonesById.get(tradeId);
    const windowRow = windowsById.get(tradeId);
    if (!auditRow || !zoneRow || !windowRow) return;
    assembled.push({
      ...(row as unknown as AuditedTrade),
      ordinal: index + 1,
      trigger_timestamp: auditRow.trigger_timestamp,
      audit: { passed: auditRow.passed, checks: auditRow.checks },
      zones: { selected: zoneRow.selected, competing: zoneRow.competing },
      bars: { one_hour: windowRow.one_hour, fifteen_minute: windowRow.fifteen_minute },
    });
  });
  return assembled;
}
```

- [ ] **Step 2: Add the hook that resolves a version/asset to a bundle**

```typescript
export type AuditStatus = 'loading' | 'loaded' | 'absent' | 'error';

/**
 * Resolve the version/asset pair to a published bundle, then fetch its audit.
 *
 * `absent` means no bundle for that pair carries the audit datasets -- which
 * is a different thing from the API being unreachable, and must not render
 * the same message.
 */
export function useStrategy04Audit(
  version: Strategy04Version,
  asset: Strategy04Asset,
): { status: AuditStatus; trades: AuditedTrade[] } {
  const [state, setState] = useState<{ status: AuditStatus; trades: AuditedTrade[] }>({
    status: 'loading',
    trades: [],
  });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', trades: [] });

    (async () => {
      const runs = await fetchRuns({ strategy_id: 'strategy_04', strategy_version: version, symbol: asset });
      const entry = runs.find((run) => run.dataset_ids.includes('trade_audit'));
      if (!entry) {
        if (!cancelled) setState({ status: 'absent', trades: [] });
        return;
      }
      const [ledger, audit, zones, windows] = await Promise.all([
        fetchDataset<LedgerDataset>(entry.bundle_id, 'trades_fixed'),
        fetchDataset<AuditDataset>(entry.bundle_id, 'trade_audit'),
        fetchDataset<ZonesDataset>(entry.bundle_id, 'zones'),
        fetchDataset<WindowsDataset>(entry.bundle_id, 'audit_windows'),
      ]);
      if (cancelled) return;
      setState({ status: 'loaded', trades: assembleAuditedTrades(ledger, audit, zones, windows) });
    })().catch(() => {
      if (!cancelled) setState({ status: 'error', trades: [] });
    });

    return () => {
      cancelled = true;
    };
  }, [version, asset]);

  return state;
}
```

- [ ] **Step 3: Point the dashboard at the new hook**

In `dashboard/src/Strategy04Dashboard.tsx`, replace the `useStrategy04Fixture` import and call with `useStrategy04Audit`, and add an `error` branch to the chart view alongside the existing `loading` and empty states. The error copy must say the catalog API is unreachable and offer the `python -m ai_trade.server --port 8080` command, matching the other screens.

- [ ] **Step 4: Typecheck and lint**

Run: `cd dashboard && npx tsc -b && npx oxlint src`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "Read the Strategy 04 audit from the catalog API"
```

---

### Task 5: Delete the fixtures and the generator

**Files:**
- Delete: `dashboard/src/fixtures/*.json`, `src/ai_trade/build_strategy_04_fixture.py`, `tests/test_build_strategy_04_fixture.py`, `tests/test_fixture_freshness.py`
- Modify: `docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md`

Task 3 imports helpers from `build_strategy_04_fixture`. Before deleting it, move `load_signals`, `load_trades`, `window`, `competing_zones`, `max_long_penetration_for`, `resolve_max_long_penetration`, and the four window-size constants into `strategy_04_audit_datasets.py`, and move their tests from `test_build_strategy_04_fixture.py` into `tests/test_strategy_04_audit_datasets.py` unchanged. Those tests encode real bugs already found — a v1 signals CSV with no penetration column, and a forgotten CLI flag silently disabling the v1.1 rule. Losing them would reopen both.

- [ ] **Step 1: Move the helpers and their tests**

Move the six functions and every test in `tests/test_build_strategy_04_fixture.py` that covers them. Do not rewrite the tests.

- [ ] **Step 2: Verify the moved tests still pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_strategy_04_audit_datasets.py -q`
Expected: the moved tests pass alongside Task 3's.

- [ ] **Step 3: Delete the fixtures and dead modules**

```bash
git rm dashboard/src/fixtures/strategy_04_v1_spy.json dashboard/src/fixtures/strategy_04_v1_qqq.json dashboard/src/fixtures/strategy_04_v1_dia.json dashboard/src/fixtures/strategy_04_v1_1_spy.json dashboard/src/fixtures/strategy_04_v1_1_qqq.json dashboard/src/fixtures/strategy_04_v1_1_dia.json
git rm src/ai_trade/build_strategy_04_fixture.py tests/test_build_strategy_04_fixture.py tests/test_fixture_freshness.py
```

`test_fixture_freshness.py` guarded the two-sources-of-truth risk. Deleting it is correct only because this task removes the second source; the bundle is now regenerated by the same run that writes the ledger.

- [ ] **Step 4: Confirm nothing still references them**

Run: `grep -rn "fixtures/strategy_04\|build_strategy_04_fixture\|useStrategy04Fixture" src dashboard/src tests`
Expected: no matches.

- [ ] **Step 5: Update the spec's status**

In `docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md`, change §9's fixture-drift risk to record that it is resolved, and mark §7 Phase 2 delivered.

- [ ] **Step 6: Full suite and build**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Run: `cd dashboard && npm run build`
Expected: all pass; the entry bundle no longer contains fixture chunks.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Drop the audit fixtures now the bundles carry the datasets"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Start the API**

Run: `./.venv/Scripts/python.exe -m ai_trade.server --port 8080`

Confirm the audit datasets are served:

Run: `./.venv/Scripts/python.exe -c "import json,urllib.request as u;r=json.load(u.urlopen('http://localhost:8080/api/runs?strategy_id=strategy_04'));print([(x['bundle_id'],'trade_audit' in x['dataset_ids']) for x in r])"`
Expected: `True` for all six Strategy 04 bundles.

- [ ] **Step 2: Drive the dashboard**

Start the dev server, open the Strategy 04 deep-dive, and confirm for SPY v1.1:

1. The trade list shows 38 rows with audit results.
2. Selecting a row updates both charts.
3. The 1-hour chart still draws the zone bands and the qualification marker.
4. Switching to QQQ and DIA loads their audits.
5. Stopping the API server and reloading shows the unreachable-API message, not an empty ledger.

- [ ] **Step 3: Confirm the bundle shrank**

Run: `cd dashboard && npm run build`
Expected: no `strategy_04_*` chunks; entry chunk at or below its current 435 kB.

- [ ] **Step 4: Commit any fixes and report**

## Completion criteria

- The six Strategy 04 bundles each declare `zones`, `trade_audit`, and `audit_windows`.
- The deep-dive renders entirely from the API; no fixture JSON remains in the repo.
- `AuditedTradeList`, `TradeSetupChart`, and `TradeExecutionChart` are unchanged by Task 4.
- Rerunning a Strategy 04 backtest and republishing updates the screen with no dashboard edit.
- `pytest -q` passes and `npm run build` succeeds.
