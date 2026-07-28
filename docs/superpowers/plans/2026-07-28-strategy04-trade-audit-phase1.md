# Strategy 04 Trade Audit — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show every Strategy 04 trade with an automated pass/fail rule audit, and let a selected trade be inspected on a 1-hour setup chart and a 15-minute execution chart, all driven by real backtest data.

**Architecture:** Audit rules live in one pure-Python module with no I/O. A generator script calls those rules over the real result CSVs, rebuilds the zone timeline with the producer's own indicator code, slices bounded bar windows, and writes a single contract-shaped JSON fixture into the dashboard. The dashboard renders from that fixture only. Phase 2 later swaps the fixture for an API response of the same shape without touching components.

**Tech Stack:** Python 3.9+, pytest 8; React 19, TypeScript, Vite, lightweight-charts 5.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md`.
- Numeric comparison tolerance is `1e-6` absolute.
- Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ`. Session rules use `America/New_York` via `zoneinfo.ZoneInfo`, matching `src/ai_trade/backtest_strategy_01.py:21`.
- JSON property names are `snake_case`.
- The dashboard never recomputes indicators, zones, or trade outcomes. It renders recorded values only.
- Existing result CSV/JSON artifacts are never modified. All new output is additive.
- Python target is 3.9: do not use `match`, `X | Y` type unions at runtime, or `dict[str, int]` in runtime-evaluated positions without `from __future__ import annotations`.
- Every new Python module starts with `from __future__ import annotations`.

---

### Task 1: Audit rule module

**Files:**
- Create: `src/ai_trade/strategy_04_audit.py`
- Test: `tests/test_strategy_04_audit.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SignalRecord`, `TradeRecord`, `CheckResult` dataclasses and `audit_trade(signal, trade, zone_qualified_timestamp, fifteen_minute_timestamps, max_long_penetration) -> list[CheckResult]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_strategy_04_audit.py`:

```python
from ai_trade.strategy_04_audit import (
    CheckResult,
    SignalRecord,
    TradeRecord,
    audit_trade,
)


def _signal(**overrides) -> SignalRecord:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        side="long",
        zone_id=39,
        zone_side="demand",
        zone_lower=437.0,
        zone_upper=437.9,
        trigger_timestamp="2021-08-03T14:15:00Z",
        trigger_low=437.5,
        one_hour_atr=1.0,
        one_hour_atr_timestamp="2021-08-03T14:00:00Z",
        stop_buffer=0.05,
        long_zone_penetration_fraction=0.2,
        reward_to_risk=1.0,
    )
    values.update(overrides)
    return SignalRecord(**values)


def _trade(**overrides) -> TradeRecord:
    values = dict(
        decision_timestamp="2021-08-03T14:30:00Z",
        entry_timestamp="2021-08-03T14:30:00Z",
        exit_timestamp="2021-08-03T15:45:00Z",
        side="long",
        entry_price=437.95,
        stop_price=436.95,
        target_price=438.95,
        exit_price=438.99,
        exit_reason="target",
        result_r=0.97,
    )
    values.update(overrides)
    return TradeRecord(**values)


TIMESTAMPS = [
    "2021-08-03T14:15:00Z",
    "2021-08-03T14:30:00Z",
    "2021-08-03T14:45:00Z",
]


def _result(results: list[CheckResult], check_id: str) -> CheckResult:
    return next(item for item in results if item.check_id == check_id)


def test_clean_trade_passes_every_check():
    results = audit_trade(_signal(), _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert [item.check_id for item in results if not item.passed] == []


def test_atr_taken_from_the_trigger_bar_fails_causality():
    signal = _signal(one_hour_atr_timestamp="2021-08-03T14:15:00Z")
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "causality_atr").passed is False


def test_zone_qualified_after_trigger_fails_causality():
    results = audit_trade(_signal(), _trade(), "2021-08-03T14:45:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "causality_zone").passed is False


def test_stop_buffer_must_be_five_percent_of_atr():
    results = audit_trade(_signal(stop_buffer=0.09), _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "stop_buffer").passed is False


def test_long_stop_sits_below_zone_lower_by_the_buffer():
    results = audit_trade(_signal(), _trade(stop_price=436.50), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "stop_price").passed is False


def test_entry_must_be_the_next_fifteen_minute_bar():
    trade = _trade(entry_timestamp="2021-08-03T14:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:45:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "entry_timing").passed is False


def test_target_must_be_one_r_from_entry():
    results = audit_trade(_signal(), _trade(target_price=440.0), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "target_price").passed is False


def test_penetration_exactly_at_the_limit_passes():
    signal = _signal(long_zone_penetration_fraction=0.25)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is True


def test_penetration_beyond_the_limit_fails():
    signal = _signal(long_zone_penetration_fraction=0.2500001)
    results = audit_trade(signal, _trade(), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is False


def test_short_trades_skip_the_penetration_gate():
    signal = _signal(side="short", zone_side="supply", long_zone_penetration_fraction=0.9)
    trade = _trade(side="short", stop_price=437.95, entry_price=436.95, target_price=435.95, exit_price=435.9)
    results = audit_trade(signal, trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "penetration").passed is True


def test_entry_before_ten_thirty_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T14:15:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T14:15:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_entry_exactly_at_ten_thirty_new_york_passes_session():
    trade = _trade(entry_timestamp="2021-08-03T14:30:00Z")
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is True


def test_entry_exactly_at_fifteen_hundred_new_york_fails_session():
    trade = _trade(entry_timestamp="2021-08-03T19:00:00Z", exit_timestamp="2021-08-03T19:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-03T19:00:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_stop_exit_priced_at_the_target_fails_outcome():
    trade = _trade(exit_reason="stop", exit_price=438.99)
    results = audit_trade(_signal(), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "outcome").passed is False


def test_friday_entry_fails_session():
    trade = _trade(entry_timestamp="2021-08-06T14:30:00Z", exit_timestamp="2021-08-06T15:45:00Z")
    results = audit_trade(_signal(entry_timestamp="2021-08-06T14:30:00Z"), trade, "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "session").passed is False


def test_target_exit_below_target_price_fails_outcome():
    results = audit_trade(_signal(), _trade(exit_price=438.0), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "outcome").passed is False


def test_demand_zone_with_short_side_fails_side_match():
    signal = _signal(side="short", zone_side="demand")
    results = audit_trade(signal, _trade(side="short"), "2021-08-03T13:00:00Z", TIMESTAMPS, 0.25)
    assert _result(results, "side_match").passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_strategy_04_audit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_trade.strategy_04_audit'`

- [ ] **Step 3: Write the implementation**

Create `src/ai_trade/strategy_04_audit.py`:

```python
"""Per-trade correctness checks for Strategy 04 historical results.

Every function is pure. A failing check means the backtest is wrong, not that
the trade was unprofitable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from zoneinfo import ZoneInfo

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EASTERN = ZoneInfo("America/New_York")
TOLERANCE = 1e-6
STOP_BUFFER_ATR_FRACTION = 0.05
SESSION_START_MINUTES = 10 * 60 + 30
SESSION_END_MINUTES = 15 * 60


@dataclass(frozen=True)
class SignalRecord:
    decision_timestamp: str
    entry_timestamp: str
    side: str
    zone_id: int
    zone_side: str
    zone_lower: float
    zone_upper: float
    trigger_timestamp: str
    trigger_low: float
    one_hour_atr: float
    one_hour_atr_timestamp: str
    stop_buffer: float
    long_zone_penetration_fraction: float
    reward_to_risk: float


@dataclass(frozen=True)
class TradeRecord:
    decision_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    side: str
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float
    exit_reason: str
    result_r: float


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    passed: bool
    expected: str
    actual: str


def _parse(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= TOLERANCE


def _check(check_id: str, passed: bool, expected: object, actual: object) -> CheckResult:
    return CheckResult(check_id, passed, str(expected), str(actual))


def check_causality_atr(signal: SignalRecord) -> CheckResult:
    passed = _parse(signal.one_hour_atr_timestamp) < _parse(signal.trigger_timestamp)
    return _check(
        "causality_atr",
        passed,
        "atr bar before " + signal.trigger_timestamp,
        signal.one_hour_atr_timestamp,
    )


def check_causality_zone(signal: SignalRecord, zone_qualified_timestamp: str) -> CheckResult:
    if not zone_qualified_timestamp:
        return _check("causality_zone", False, "a qualification timestamp", "missing")
    passed = _parse(zone_qualified_timestamp) < _parse(signal.trigger_timestamp)
    return _check(
        "causality_zone",
        passed,
        "qualified before " + signal.trigger_timestamp,
        zone_qualified_timestamp,
    )


def check_stop_buffer(signal: SignalRecord) -> CheckResult:
    expected = STOP_BUFFER_ATR_FRACTION * signal.one_hour_atr
    return _check("stop_buffer", _close(expected, signal.stop_buffer), expected, signal.stop_buffer)


def check_stop_price(signal: SignalRecord, trade: TradeRecord) -> CheckResult:
    if trade.side == "long":
        expected = signal.zone_lower - signal.stop_buffer
    else:
        expected = signal.zone_upper + signal.stop_buffer
    return _check("stop_price", _close(expected, trade.stop_price), expected, trade.stop_price)


def check_entry_timing(
    trade: TradeRecord,
    signal: SignalRecord,
    fifteen_minute_timestamps: Sequence[str],
) -> CheckResult:
    ordered = sorted(fifteen_minute_timestamps)
    later = [value for value in ordered if _parse(value) > _parse(signal.trigger_timestamp)]
    if not later:
        return _check("entry_timing", False, "a bar after the trigger", "none available")
    expected = later[0]
    return _check("entry_timing", expected == trade.entry_timestamp, expected, trade.entry_timestamp)


def check_target_price(signal: SignalRecord, trade: TradeRecord) -> CheckResult:
    distance = abs(trade.entry_price - trade.stop_price)
    if trade.side == "long":
        expected = trade.entry_price + distance
    else:
        expected = trade.entry_price - distance
    passed = _close(expected, trade.target_price) and _close(signal.reward_to_risk, 1.0)
    return _check("target_price", passed, expected, trade.target_price)


def check_penetration(signal: SignalRecord, max_long_penetration: float) -> CheckResult:
    if signal.side != "long":
        return _check("penetration", True, "not applicable to shorts", signal.side)
    passed = signal.long_zone_penetration_fraction <= max_long_penetration + TOLERANCE
    return _check(
        "penetration",
        passed,
        "at most " + str(max_long_penetration),
        signal.long_zone_penetration_fraction,
    )


def check_session(trade: TradeRecord) -> CheckResult:
    local = _parse(trade.entry_timestamp).astimezone(EASTERN)
    minutes = local.hour * 60 + local.minute
    passed = (
        local.weekday() < 4
        and SESSION_START_MINUTES <= minutes < SESSION_END_MINUTES
    )
    return _check(
        "session",
        passed,
        "monday-thursday, 10:30 to 15:00 new york",
        local.strftime("%a %H:%M"),
    )


def check_outcome(trade: TradeRecord) -> CheckResult:
    if trade.exit_reason == "target":
        passed = (
            trade.exit_price >= trade.target_price - TOLERANCE
            if trade.side == "long"
            else trade.exit_price <= trade.target_price + TOLERANCE
        )
        expected = "at or beyond target " + str(trade.target_price)
    elif trade.exit_reason == "stop":
        passed = (
            trade.exit_price <= trade.stop_price + TOLERANCE
            if trade.side == "long"
            else trade.exit_price >= trade.stop_price - TOLERANCE
        )
        expected = "at or beyond stop " + str(trade.stop_price)
    else:
        return _check("outcome", True, "no level assertion", trade.exit_reason)
    return _check("outcome", passed, expected, trade.exit_price)


def check_side_match(signal: SignalRecord) -> CheckResult:
    expected = "demand" if signal.side == "long" else "supply"
    return _check("side_match", expected == signal.zone_side, expected, signal.zone_side)


def audit_trade(
    signal: SignalRecord,
    trade: TradeRecord,
    zone_qualified_timestamp: str,
    fifteen_minute_timestamps: Sequence[str],
    max_long_penetration: float,
) -> list[CheckResult]:
    """Run every check for one trade, in stable order."""

    return [
        check_causality_atr(signal),
        check_causality_zone(signal, zone_qualified_timestamp),
        check_stop_buffer(signal),
        check_stop_price(signal, trade),
        check_entry_timing(trade, signal, fifteen_minute_timestamps),
        check_target_price(signal, trade),
        check_penetration(signal, max_long_penetration),
        check_session(trade),
        check_outcome(trade),
        check_side_match(signal),
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_strategy_04_audit.py -q`
Expected: `17 passed`

- [ ] **Step 5: Run the whole suite to confirm nothing regressed**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: `90 passed`

- [ ] **Step 6: Commit**

```bash
git add src/ai_trade/strategy_04_audit.py tests/test_strategy_04_audit.py
git commit -m "feat: add Strategy 04 per-trade audit checks"
```

---

### Task 2: Fixture generator

**Files:**
- Create: `src/ai_trade/build_strategy_04_fixture.py`
- Create: `dashboard/src/fixtures/strategy_04_v1_1_spy.json` (generated output, committed)
- Test: `tests/test_build_strategy_04_fixture.py`

**Interfaces:**
- Consumes: `SignalRecord`, `TradeRecord`, `audit_trade` from Task 1.
- Produces: `load_signals(path) -> list[SignalRecord]`, `load_trades(path) -> list[TradeRecord]`, `window(bars, start, end, before, after) -> list[OHLCVBar]`, `build_fixture(...) -> dict`, and the JSON file consumed by Tasks 3-7.

The generator rebuilds the zone timeline by calling `build_one_hour_indicator` from `src/ai_trade/strategy_04_indicator.py:723` with `strategy_04_v0_3_parameters()`. This is the producer's own code, so `qualified_timestamp` and competing zones come from the same logic that produced the trades. `Zone` already carries `qualified_timestamp` (`src/ai_trade/strategy_04_indicator.py:137`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_strategy_04_fixture.py`:

```python
import json
from pathlib import Path

from ai_trade.build_strategy_04_fixture import (
    load_signals,
    load_trades,
    window,
)
from ai_trade.market_data import OHLCVBar

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "strategies" / "strategy_04" / "v1_1" / "results" / "spy_1h_15m"
FIXTURE = REPO_ROOT / "dashboard" / "src" / "fixtures" / "strategy_04_v1_1_spy.json"


def _bars() -> list[OHLCVBar]:
    return [
        OHLCVBar("2021-08-03T14:%02d:00Z" % minute, 1.0, 2.0, 0.5, 1.5, 10.0)
        for minute in range(0, 60, 15)
    ]


def test_window_clips_at_the_start_of_the_series():
    selected = window(_bars(), "2021-08-03T14:00:00Z", "2021-08-03T14:15:00Z", 5, 1)
    assert [bar.timestamp for bar in selected] == [
        "2021-08-03T14:00:00Z",
        "2021-08-03T14:15:00Z",
        "2021-08-03T14:30:00Z",
    ]


def test_window_clips_at_the_end_of_the_series():
    selected = window(_bars(), "2021-08-03T14:30:00Z", "2021-08-03T14:45:00Z", 1, 5)
    assert [bar.timestamp for bar in selected] == [
        "2021-08-03T14:15:00Z",
        "2021-08-03T14:30:00Z",
        "2021-08-03T14:45:00Z",
    ]


def test_signals_and_trades_join_on_decision_timestamp():
    signals = load_signals(RESULTS / "candidate_signals.csv")
    trades = load_trades(RESULTS / "fixed_trades.csv")
    signal_keys = {signal.decision_timestamp for signal in signals}
    assert {trade.decision_timestamp for trade in trades} <= signal_keys


def test_fixture_reconciles_with_the_backtest_report():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = json.loads((RESULTS / "fixed_summary.json").read_text(encoding="utf-8"))
    assert len(fixture["trades"]) == summary["trades"]
    assert abs(fixture["summary"]["net_pnl"] - summary["net_pnl"]) < 1e-6
    assert abs(fixture["summary"]["ending_equity"] - summary["ending_equity"]) < 1e-6


def test_every_trade_carries_zones_and_bar_windows():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for trade in fixture["trades"]:
        assert trade["zones"]["selected"]["zone_id"] > 0
        assert len(trade["bars"]["one_hour"]) > 0
        assert len(trade["bars"]["fifteen_minute"]) > 0
        assert len(trade["audit"]["checks"]) == 10
```

- [ ] **Step 2: Confirm the summary field names before coding**

Run: `./.venv/Scripts/python.exe -c "import json;print(sorted(json.load(open('strategies/strategy_04/v1_1/results/spy_1h_15m/fixed_summary.json')).keys()))"`
Expected: a key list including `trades`, `net_pnl`, and `ending_equity`. If any of those three names differ, update both the test above and `build_fixture` to the actual names before continuing.

- [ ] **Step 3: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_build_strategy_04_fixture.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ai_trade.build_strategy_04_fixture'`

- [ ] **Step 4: Write the implementation**

Create `src/ai_trade/build_strategy_04_fixture.py`:

```python
"""Build the Strategy 04 dashboard fixture from real backtest artifacts.

Phase 1 of docs/superpowers/specs/2026-07-28-strategy04-trade-audit-design.md.
Output shape matches the visualization contract so Phase 2 can serve the same
JSON from the API with no dashboard component changes.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_audit import (
    CheckResult,
    SignalRecord,
    TradeRecord,
    audit_trade,
)
from ai_trade.strategy_04_indicator import (
    Zone,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SCHEMA_VERSION = "1.0.0"
ONE_HOUR_BARS_BEFORE = 40
ONE_HOUR_BARS_AFTER = 10
FIFTEEN_MINUTE_BARS_BEFORE = 20
FIFTEEN_MINUTE_BARS_AFTER = 20
MAX_LONG_PENETRATION = 0.25


def _parse(timestamp: str) -> datetime:
    return datetime.strptime(timestamp, UTC_FORMAT).replace(tzinfo=timezone.utc)


def load_signals(path: Path) -> list[SignalRecord]:
    """Read candidate_signals.csv into typed records."""

    records: list[SignalRecord] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(
                SignalRecord(
                    decision_timestamp=row["decision_timestamp"],
                    entry_timestamp=row["entry_timestamp"],
                    side=row["side"],
                    zone_id=int(row["zone_id"]),
                    zone_side=row["zone_side"],
                    zone_lower=float(row["zone_lower"]),
                    zone_upper=float(row["zone_upper"]),
                    trigger_timestamp=row["trigger_timestamp"],
                    trigger_low=float(row["trigger_low"]),
                    one_hour_atr=float(row["one_hour_atr"]),
                    one_hour_atr_timestamp=row["one_hour_atr_timestamp"],
                    stop_buffer=float(row["stop_buffer"]),
                    long_zone_penetration_fraction=float(row["long_zone_penetration_fraction"]),
                    reward_to_risk=float(row["reward_to_risk"]),
                )
            )
    return records


def load_trades(path: Path) -> list[TradeRecord]:
    """Read a trade ledger CSV into typed records."""

    records: list[TradeRecord] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            records.append(
                TradeRecord(
                    decision_timestamp=row["decision_timestamp"],
                    entry_timestamp=row["entry_timestamp"],
                    exit_timestamp=row["exit_timestamp"],
                    side=row["side"],
                    entry_price=float(row["entry_price"]),
                    stop_price=float(row["stop_price"]),
                    target_price=float(row["target_price"]),
                    exit_price=float(row["exit_price"]),
                    exit_reason=row["exit_reason"],
                    result_r=float(row["result_r"]),
                )
            )
    return records


def window(
    bars: Sequence[OHLCVBar],
    start: str,
    end: str,
    before: int,
    after: int,
) -> list[OHLCVBar]:
    """Return bars spanning start..end, padded and clipped to the series."""

    start_at = _parse(start)
    end_at = _parse(end)
    inside = [index for index, bar in enumerate(bars) if start_at <= _parse(bar.timestamp) <= end_at]
    if not inside:
        return []
    first = max(0, inside[0] - before)
    last = min(len(bars), inside[-1] + after + 1)
    return list(bars[first:last])


def _bar_json(bar: OHLCVBar) -> dict:
    return {
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _zone_json(zone: Zone) -> dict:
    return {
        "zone_id": zone.zone_id,
        "side": zone.side,
        "lower": zone.lower,
        "upper": zone.upper,
        "qualified_timestamp": zone.qualified_timestamp or "",
        "score": zone.qualification_score,
        "status": zone.status,
    }


def _zone_by_id(zones: Sequence[Zone], zone_id: int) -> Optional[Zone]:
    for zone in zones:
        if zone.zone_id == zone_id:
            return zone
    return None


def competing_zones(zones: Sequence[Zone], selected: Zone, trigger_timestamp: str) -> list[Zone]:
    """Zones qualified before the trigger that overlap the selected zone's range."""

    trigger_at = _parse(trigger_timestamp)
    results: list[Zone] = []
    for zone in zones:
        if zone.zone_id == selected.zone_id or not zone.qualified_timestamp:
            continue
        if _parse(zone.qualified_timestamp) >= trigger_at:
            continue
        if zone.break_timestamp and _parse(zone.break_timestamp) < trigger_at:
            continue
        if zone.invalidated_timestamp and _parse(zone.invalidated_timestamp) < trigger_at:
            continue
        if zone.lower <= selected.upper and zone.upper >= selected.lower:
            results.append(zone)
    return results


def _check_json(check: CheckResult) -> dict:
    return {
        "check_id": check.check_id,
        "passed": check.passed,
        "expected": check.expected,
        "actual": check.actual,
    }


def build_fixture(
    results_dir: Path,
    one_hour_path: Path,
    fifteen_minute_path: Path,
    symbol: str,
    strategy_version: str,
) -> dict:
    """Assemble the complete fixture document."""

    signals = {signal.decision_timestamp: signal for signal in load_signals(results_dir / "candidate_signals.csv")}
    trades = load_trades(results_dir / "fixed_trades.csv")
    summary = json.loads((results_dir / "fixed_summary.json").read_text(encoding="utf-8"))

    hour_bars = load_ohlcv_csv(one_hour_path)
    minute_bars = load_ohlcv_csv(fifteen_minute_path)
    minute_timestamps = [bar.timestamp for bar in minute_bars]

    indicator = build_one_hour_indicator(hour_bars, strategy_04_v0_3_parameters())

    trade_documents = []
    for ordinal, trade in enumerate(trades, start=1):
        signal = signals[trade.decision_timestamp]
        selected = _zone_by_id(indicator.zones, signal.zone_id)
        if selected is None:
            raise ValueError("Zone %d referenced by %s is missing" % (signal.zone_id, trade.decision_timestamp))

        checks = audit_trade(
            signal,
            trade,
            selected.qualified_timestamp or "",
            minute_timestamps,
            MAX_LONG_PENETRATION,
        )
        hour_window_start = selected.qualified_timestamp or trade.entry_timestamp
        trade_documents.append(
            {
                "trade_id": "%s_%s:fixed:%06d" % (strategy_version, symbol.lower(), ordinal),
                "ordinal": ordinal,
                "decision_timestamp": trade.decision_timestamp,
                "entry_timestamp": trade.entry_timestamp,
                "exit_timestamp": trade.exit_timestamp,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "stop_price": trade.stop_price,
                "target_price": trade.target_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "result_r": trade.result_r,
                "trigger_timestamp": signal.trigger_timestamp,
                "audit": {
                    "passed": all(check.passed for check in checks),
                    "checks": [_check_json(check) for check in checks],
                },
                "zones": {
                    "selected": _zone_json(selected),
                    "competing": [
                        _zone_json(zone)
                        for zone in competing_zones(indicator.zones, selected, signal.trigger_timestamp)
                    ],
                },
                "bars": {
                    "one_hour": [
                        _bar_json(bar)
                        for bar in window(
                            hour_bars,
                            hour_window_start,
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
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": "strategy_04_%s_%s_1h_15m" % (strategy_version, symbol.lower()),
        "execution_authority": "none",
        "run": {"strategy_id": "strategy_04", "strategy_version": strategy_version},
        "instrument": {"symbol": symbol},
        "summary": {
            "trade_count": len(trade_documents),
            "audit_passed": sum(1 for item in trade_documents if item["audit"]["passed"]),
            "audit_failed": sum(1 for item in trade_documents if not item["audit"]["passed"]),
            "net_pnl": summary["net_pnl"],
            "ending_equity": summary["ending_equity"],
        },
        "trades": trade_documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("strategies/strategy_04/v1_1/results/spy_1h_15m"))
    parser.add_argument("--one-hour", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"))
    parser.add_argument("--fifteen-minute", type=Path, default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"))
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--strategy-version", default="v1_1")
    parser.add_argument("--output", type=Path, default=Path("dashboard/src/fixtures/strategy_04_v1_1_spy.json"))
    args = parser.parse_args()

    fixture = build_fixture(
        args.results,
        args.one_hour,
        args.fifteen_minute,
        args.symbol,
        args.strategy_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Wrote %s with %d trades" % (args.output, len(fixture["trades"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Generate the fixture**

Run: `./.venv/Scripts/python.exe -m ai_trade.build_strategy_04_fixture`
Expected: `Wrote dashboard\src\fixtures\strategy_04_v1_1_spy.json with 38 trades`

If it raises `ValueError: Zone N referenced by ... is missing`, the rebuilt zone timeline does not match the one the backtest used. Stop and report this rather than working around it — it means the indicator parameters differ from the recorded run, and the fixture would be untrustworthy.

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_build_strategy_04_fixture.py -q`
Expected: `5 passed`

- [ ] **Step 7: Inspect the audit outcome**

Run: `./.venv/Scripts/python.exe -c "import json;d=json.load(open('dashboard/src/fixtures/strategy_04_v1_1_spy.json'));print(d['summary']);[print(t['ordinal'],[c['check_id'] for c in t['audit']['checks'] if not c['passed']]) for t in d['trades'] if not t['audit']['passed']]"`
Expected: the summary line, then one line per failing trade. Record what this prints — it is the first real answer to "was this trade correct".

- [ ] **Step 8: Commit**

```bash
git add src/ai_trade/build_strategy_04_fixture.py tests/test_build_strategy_04_fixture.py dashboard/src/fixtures/strategy_04_v1_1_spy.json
git commit -m "feat: generate Strategy 04 audit fixture from real backtest data"
```

---

### Task 3: Dashboard fixture types and loader

**Files:**
- Create: `dashboard/src/strategy04Fixture.ts`
- Modify: `dashboard/src/types.ts`

**Interfaces:**
- Consumes: `dashboard/src/fixtures/strategy_04_v1_1_spy.json` from Task 2.
- Produces: types `AuditCheck`, `AuditResult`, `FixtureZone`, `FixtureBar`, `AuditedTrade`, `Strategy04Fixture`; and `STRATEGY_04_FIXTURE`, `toChartBars(bars)`.

- [ ] **Step 1: Add the fixture types**

Create `dashboard/src/strategy04Fixture.ts`:

```typescript
import fixture from './fixtures/strategy_04_v1_1_spy.json';
import type { Bar, ExitReason, TradeSide } from './types';

export interface AuditCheck {
  check_id: string;
  passed: boolean;
  expected: string;
  actual: string;
}

export interface AuditResult {
  passed: boolean;
  checks: AuditCheck[];
}

export interface FixtureZone {
  zone_id: number;
  side: 'demand' | 'supply';
  lower: number;
  upper: number;
  qualified_timestamp: string;
  score: number;
  status: string;
}

export interface FixtureBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AuditedTrade {
  trade_id: string;
  ordinal: number;
  decision_timestamp: string;
  entry_timestamp: string;
  exit_timestamp: string;
  side: TradeSide;
  entry_price: number;
  stop_price: number;
  target_price: number;
  exit_price: number;
  exit_reason: ExitReason;
  result_r: number;
  trigger_timestamp: string;
  audit: AuditResult;
  zones: { selected: FixtureZone; competing: FixtureZone[] };
  bars: { one_hour: FixtureBar[]; fifteen_minute: FixtureBar[] };
}

export interface Strategy04Fixture {
  schema_version: string;
  bundle_id: string;
  execution_authority: string;
  run: { strategy_id: string; strategy_version: string };
  instrument: { symbol: string };
  summary: {
    trade_count: number;
    audit_passed: number;
    audit_failed: number;
    net_pnl: number;
    ending_equity: number;
  };
  trades: AuditedTrade[];
}

export const STRATEGY_04_FIXTURE = fixture as unknown as Strategy04Fixture;

export const toEpochSeconds = (timestamp: string): number =>
  Math.floor(new Date(timestamp).getTime() / 1000);

export const toChartBars = (bars: FixtureBar[]): Bar[] =>
  bars.map((bar) => ({
    time: toEpochSeconds(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  }));

export const failedChecks = (trade: AuditedTrade): AuditCheck[] =>
  trade.audit.checks.filter((check) => !check.passed);
```

- [ ] **Step 2: Enable JSON imports**

Confirm `dashboard/tsconfig.app.json` contains `"resolveJsonModule": true` inside `compilerOptions`. If absent, add it.

Run: `node -e "const c=require('fs').readFileSync('dashboard/tsconfig.app.json','utf8');console.log(c.includes('resolveJsonModule'))"`
Expected: `true`

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/strategy04Fixture.ts dashboard/tsconfig.app.json
git commit -m "feat: add typed Strategy 04 audit fixture loader"
```

---

### Task 4: Audited trade list

**Files:**
- Create: `dashboard/src/components/AuditedTradeList.tsx`

**Interfaces:**
- Consumes: `AuditedTrade`, `failedChecks` from Task 3.
- Produces: `<AuditedTradeList trades selectedTradeId onSelect />`.

- [ ] **Step 1: Write the component**

Create `dashboard/src/components/AuditedTradeList.tsx`:

```typescript
import type { AuditedTrade } from '../strategy04Fixture';
import { failedChecks } from '../strategy04Fixture';

interface Props {
  trades: AuditedTrade[];
  selectedTradeId: string | null;
  onSelect: (tradeId: string) => void;
}

const shortTime = (timestamp: string) => timestamp.replace('T', ' ').replace(':00Z', '');

export function AuditedTradeList({ trades, selectedTradeId, onSelect }: Props) {
  const failing = trades.filter((trade) => !trade.audit.passed).length;

  return (
    <section className="s4-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div>
          <div className="s4-eyebrow">Trade ledger</div>
          <h2 className="mt-1 text-base font-semibold text-slate-950">
            {trades.length} trades
          </h2>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">
            {trades.length - failing} checks passed
          </span>
          {failing > 0 && (
            <span className="rounded bg-rose-50 px-2 py-1 text-rose-700">
              {failing} need review
            </span>
          )}
        </div>
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">#</th>
              <th className="px-4 py-2 font-medium">Entry</th>
              <th className="px-4 py-2 font-medium">Side</th>
              <th className="px-4 py-2 font-medium text-right">R</th>
              <th className="px-4 py-2 font-medium">Outcome</th>
              <th className="px-4 py-2 font-medium">Audit</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => {
              const failed = failedChecks(trade);
              const isSelected = trade.trade_id === selectedTradeId;
              return (
                <tr
                  key={trade.trade_id}
                  onClick={() => onSelect(trade.trade_id)}
                  className={`cursor-pointer border-t border-slate-100 ${
                    isSelected ? 'bg-sky-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-slate-500">{trade.ordinal}</td>
                  <td className="px-4 py-2 font-mono">{shortTime(trade.entry_timestamp)}</td>
                  <td className="px-4 py-2 capitalize">{trade.side}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {trade.result_r >= 0 ? '+' : ''}
                    {trade.result_r.toFixed(2)}
                  </td>
                  <td
                    className={`px-4 py-2 ${
                      trade.exit_reason === 'target' ? 'text-emerald-700' : 'text-rose-700'
                    }`}
                  >
                    {trade.exit_reason}
                  </td>
                  <td className="px-4 py-2">
                    {failed.length === 0 ? (
                      <span className="text-emerald-700">pass</span>
                    ) : (
                      <span className="text-rose-700" title={failed.map((c) => c.check_id).join(', ')}>
                        {failed.map((c) => c.check_id).join(', ')}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/AuditedTradeList.tsx
git commit -m "feat: add audited trade list with per-trade check results"
```

---

### Task 5: Shared trade-chart hook

**Files:**
- Create: `dashboard/src/components/useTradeChart.ts`

**Interfaces:**
- Consumes: `FixtureBar`, `toChartBars` from Task 3.
- Produces: `useTradeChart(bars, decorate) -> RefObject<HTMLDivElement>`, and the `TradeChartHandles` type carrying `chart`, `candles`, `span`, `drawLevel`, and `setMarkers`.

Tasks 6 and 7 both need identical chart construction, price-level drawing, and resize handling. That logic lives here once. Only the decoration differs between the two charts.

- [ ] **Step 1: Write the hook**

Create `dashboard/src/components/useTradeChart.ts`:

```typescript
import { useEffect, useRef } from 'react';
import { CandlestickSeries, LineSeries, createChart } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, SeriesMarker, Time } from 'lightweight-charts';
import type { FixtureBar } from '../strategy04Fixture';
import { toChartBars } from '../strategy04Fixture';

export interface TradeChartHandles {
  chart: IChartApi;
  candles: ISeriesApi<'Candlestick'>;
  span: Time[];
  drawLevel: (price: number, color: string, dotted: boolean, title: string) => void;
  setMarkers: (markers: SeriesMarker<Time>[]) => void;
}

const CHART_OPTIONS = {
  layout: { background: { color: '#ffffff' }, textColor: '#64748b', fontSize: 11 },
  grid: { vertLines: { color: '#eef2f7' }, horzLines: { color: '#eef2f7' } },
  rightPriceScale: { borderColor: '#dbe3ee', scaleMargins: { top: 0.12, bottom: 0.12 } },
  timeScale: { borderColor: '#dbe3ee', timeVisible: true, secondsVisible: false },
};

const CANDLE_OPTIONS = {
  upColor: '#0f9f74',
  downColor: '#e24c63',
  borderUpColor: '#0f9f74',
  borderDownColor: '#e24c63',
  wickUpColor: '#0f9f74',
  wickDownColor: '#e24c63',
};

/**
 * Build a candlestick chart from fixture bars and hand the caller the pieces
 * it needs to draw price levels and markers on top.
 */
export function useTradeChart(
  bars: FixtureBar[],
  lineWidth: 1 | 2,
  decorate: (handles: TradeChartHandles) => void,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const decorateRef = useRef(decorate);
  decorateRef.current = decorate;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, CHART_OPTIONS);
    const chartBars = toChartBars(bars);
    const candles = chart.addSeries(CandlestickSeries, CANDLE_OPTIONS);
    candles.setData(
      chartBars.map((bar) => ({
        time: bar.time as Time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );

    const span = chartBars.map((bar) => bar.time as Time);
    const drawLevel = (price: number, color: string, dotted: boolean, title: string) => {
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth,
        lineStyle: dotted ? 2 : 0,
        priceLineVisible: false,
        lastValueVisible: true,
        title,
      });
      series.setData(span.map((time) => ({ time, value: price })));
    };

    decorateRef.current({
      chart,
      candles,
      span,
      drawLevel,
      setMarkers: (markers) => candles.setMarkers(markers),
    });

    chart.timeScale().fitContent();

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    };
    resize();
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      chart.remove();
    };
  }, [bars, lineWidth]);

  return containerRef;
}
```

- [ ] **Step 2: Verify the markers API against the installed library**

lightweight-charts 5 moved markers to a plugin in some builds. Run:

`node -e "console.log(require('./dashboard/node_modules/lightweight-charts/package.json').version)"`

If Step 3's build errors with `setMarkers is not a function` or `SeriesMarker` is not exported, replace the `setMarkers` implementation with the v5 plugin API: `import { createSeriesMarkers } from 'lightweight-charts'` and `setMarkers: (markers) => { createSeriesMarkers(candles, markers); }`, typing `markers` as the plugin's marker type. Make the change here only — both consuming charts go through this hook.

- [ ] **Step 3: Verify it compiles**

Run: `cd dashboard && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/useTradeChart.ts
git commit -m "feat: add shared trade-chart hook for the audit charts"
```

---

### Task 6: One-hour setup chart

**Files:**
- Create: `dashboard/src/components/TradeSetupChart.tsx`

**Interfaces:**
- Consumes: `AuditedTrade`, `toEpochSeconds` from Task 3; `useTradeChart` from Task 5.
- Produces: `<TradeSetupChart trade />`.

Zone bands are drawn as two lines at the zone's lower and upper prices, because lightweight-charts 5 has no native rectangle primitive. The selected zone uses solid lines; competing zones use dotted lines.

- [ ] **Step 1: Write the component**

Create `dashboard/src/components/TradeSetupChart.tsx`:

```typescript
import type { SeriesMarker, Time } from 'lightweight-charts';
import type { AuditedTrade } from '../strategy04Fixture';
import { toEpochSeconds } from '../strategy04Fixture';
import { useTradeChart } from './useTradeChart';

interface Props {
  trade: AuditedTrade;
}

export function TradeSetupChart({ trade }: Props) {
  const containerRef = useTradeChart(trade.bars.one_hour, 1, ({ drawLevel, setMarkers }) => {
    const zone = trade.zones.selected;
    drawLevel(zone.lower, '#0f9f74', false, `zone ${zone.lower.toFixed(2)}`);
    drawLevel(zone.upper, '#0f9f74', false, `score ${zone.score}`);
    trade.zones.competing.forEach((competitor) => {
      drawLevel(competitor.lower, '#94a3b8', true, `#${competitor.zone_id} score ${competitor.score}`);
      drawLevel(competitor.upper, '#94a3b8', true, '');
    });

    const markers: SeriesMarker<Time>[] = [];
    if (zone.qualified_timestamp) {
      markers.push({
        time: toEpochSeconds(zone.qualified_timestamp) as Time,
        position: 'aboveBar',
        color: '#185fa5',
        shape: 'arrowDown',
        text: 'zone qualified',
      });
    }
    markers.push({
      time: toEpochSeconds(trade.trigger_timestamp) as Time,
      position: 'belowBar',
      color: '#ba7517',
      shape: 'arrowUp',
      text: 'trigger',
    });
    setMarkers(markers);
  });

  return (
    <section className="s4-panel overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="s4-eyebrow">1 hour — the setup</div>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          Why trade {trade.ordinal} was allowed to exist
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          {trade.zones.selected.side} zone {trade.zones.selected.lower.toFixed(2)}–
          {trade.zones.selected.upper.toFixed(2)} · score {trade.zones.selected.score} ·{' '}
          {trade.zones.competing.length} competing zone(s) shown dotted
        </p>
      </div>
      <div ref={containerRef} className="h-[320px] w-full bg-white" />
    </section>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/TradeSetupChart.tsx
git commit -m "feat: add 1h setup chart with zone bands and causality markers"
```

---

### Task 7: Fifteen-minute execution chart

**Files:**
- Create: `dashboard/src/components/TradeExecutionChart.tsx`

**Interfaces:**
- Consumes: `AuditedTrade`, `toEpochSeconds` from Task 3; `useTradeChart` from Task 5.
- Produces: `<TradeExecutionChart trade />`.

- [ ] **Step 1: Write the component**

Create `dashboard/src/components/TradeExecutionChart.tsx`:

```typescript
import type { SeriesMarker, Time } from 'lightweight-charts';
import type { AuditedTrade } from '../strategy04Fixture';
import { toEpochSeconds } from '../strategy04Fixture';
import { useTradeChart } from './useTradeChart';

interface Props {
  trade: AuditedTrade;
}

export function TradeExecutionChart({ trade }: Props) {
  const containerRef = useTradeChart(trade.bars.fifteen_minute, 2, ({ drawLevel, setMarkers }) => {
    drawLevel(trade.target_price, '#1d9e75', true, `target ${trade.target_price.toFixed(2)}`);
    drawLevel(trade.entry_price, '#378add', false, `entry ${trade.entry_price.toFixed(2)}`);
    drawLevel(trade.stop_price, '#e24b4a', true, `stop ${trade.stop_price.toFixed(2)}`);

    const markers: SeriesMarker<Time>[] = [
      {
        time: toEpochSeconds(trade.trigger_timestamp) as Time,
        position: 'belowBar',
        color: '#639922',
        shape: 'arrowUp',
        text: 'trigger',
      },
      {
        time: toEpochSeconds(trade.entry_timestamp) as Time,
        position: 'belowBar',
        color: '#378add',
        shape: 'arrowUp',
        text: 'entry',
      },
      {
        time: toEpochSeconds(trade.exit_timestamp) as Time,
        position: 'aboveBar',
        color: trade.exit_reason === 'target' ? '#1d9e75' : '#e24b4a',
        shape: 'arrowDown',
        text: `${trade.exit_reason} ${trade.result_r >= 0 ? '+' : ''}${trade.result_r.toFixed(2)}R`,
      },
    ];
    setMarkers(markers);
  });

  return (
    <section className="s4-panel overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="s4-eyebrow">15 minutes — the execution</div>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          What happened to trade {trade.ordinal}
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Entry {trade.entry_price.toFixed(2)} · stop {trade.stop_price.toFixed(2)} · target{' '}
          {trade.target_price.toFixed(2)} · exited at {trade.exit_price.toFixed(2)} by {trade.exit_reason}
        </p>
      </div>
      <div ref={containerRef} className="h-[320px] w-full bg-white" />
    </section>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd dashboard && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/TradeExecutionChart.tsx
git commit -m "feat: add 15m execution chart with entry, stop, target and exit"
```

---

### Task 8: Wire the audit view into the dashboard and delete the mocks

**Files:**
- Modify: `dashboard/src/Strategy04Dashboard.tsx:16` (import), `:359-361` (mock data), `:541-556` (chart view)
- Modify: `dashboard/src/mockData.ts`

**Interfaces:**
- Consumes: `AuditedTradeList` (Task 4), `TradeSetupChart` (Task 6), `TradeExecutionChart` (Task 7), `STRATEGY_04_FIXTURE` (Task 3).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Replace the mock data wiring**

In `dashboard/src/Strategy04Dashboard.tsx`, delete the line:

```typescript
import { generateMockBars, MOCK_TRADES_S4 } from './mockData';
```

and add:

```typescript
import { STRATEGY_04_FIXTURE } from './strategy04Fixture';
import { AuditedTradeList } from './components/AuditedTradeList';
import { TradeSetupChart } from './components/TradeSetupChart';
import { TradeExecutionChart } from './components/TradeExecutionChart';
```

- [ ] **Step 2: Replace the mock state**

Replace these two lines (currently at `dashboard/src/Strategy04Dashboard.tsx:359-361`):

```typescript
  const bars = useMemo(() => generateMockBars(), []);
  const trades = asset === 'SPY' ? MOCK_TRADES_S4 : [];
```

with:

```typescript
  const auditedTrades = useMemo(
    () =>
      asset === 'SPY' && version === 'v1_1' ? STRATEGY_04_FIXTURE.trades : [],
    [asset, version],
  );
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const selectedTrade = useMemo(
    () => auditedTrades.find((trade) => trade.trade_id === selectedTradeId) ?? auditedTrades[0] ?? null,
    [auditedTrades, selectedTradeId],
  );
```

- [ ] **Step 3: Replace the chart view body**

Replace the whole `{view === 'chart' && ( ... )}` block with:

```typescript
          {view === 'chart' && (
            <div className="space-y-5">
              {auditedTrades.length === 0 ? (
                <section className="s4-panel p-8 text-center">
                  <div className="text-sm font-semibold text-slate-900">
                    Audit fixture not generated for {asset} {version}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Run <code>python -m ai_trade.build_strategy_04_fixture</code> for this
                    symbol and version to populate the trade audit.
                  </p>
                </section>
              ) : (
                <>
                  <AuditedTradeList
                    trades={auditedTrades}
                    selectedTradeId={selectedTrade ? selectedTrade.trade_id : null}
                    onSelect={setSelectedTradeId}
                  />
                  {selectedTrade && (
                    <>
                      <TradeSetupChart trade={selectedTrade} />
                      <TradeExecutionChart trade={selectedTrade} />
                    </>
                  )}
                </>
              )}
            </div>
          )}
```

- [ ] **Step 4: Delete the mock generators**

In `dashboard/src/mockData.ts`, delete the `generateMockBars` function and the `MOCK_TRADES_S4` constant, plus any imports left unused by their removal.

Run: `cd dashboard && npx oxlint src`
Expected: no unused-import or no-undef errors.

- [ ] **Step 5: Build and confirm no dead references remain**

Run: `cd dashboard && npm run build`
Expected: build succeeds.

Run: `node -e "const c=require('fs').readFileSync('dashboard/src/Strategy04Dashboard.tsx','utf8');console.log(c.includes('MOCK_TRADES_S4')||c.includes('generateMockBars'))"`
Expected: `false`

- [ ] **Step 6: Run the dashboard and verify against the fixture**

Run: `cd dashboard && npm run dev`

Open the Strategy 04 dashboard, select SPY and v1.1, and open the "Chart & trades" tab. Confirm all of the following:

1. The trade list shows 38 rows.
2. The header count matches `summary.audit_passed` and `summary.audit_failed` from the fixture.
3. Clicking a row updates both charts.
4. The 1-hour chart shows the zone lines and the "zone qualified" marker.
5. The 15-minute chart shows entry, stop and target lines, and the exit marker names the same `exit_reason` as the row.

- [ ] **Step 7: Run the full Python suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: `95 passed`

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/Strategy04Dashboard.tsx dashboard/src/mockData.ts
git commit -m "feat: replace Strategy 04 mock chart with real audited trade view"
```

---

## Phase 1 completion criteria

- Every Strategy 04 v1.1 SPY trade is listed with a pass/fail audit result.
- Selecting a trade drives both charts.
- No mock bars or mock trades remain anywhere in the dashboard.
- Every value drawn on either chart traces to a recorded producer field.
- `pytest -q` passes and `npm run build` succeeds.

Phase 2 is out of scope for this plan. It replaces the fixture import in
`dashboard/src/strategy04Fixture.ts` with a fetch against `/api/runs`, with no
changes to the Task 4, 5, 6, and 7 components.

## Known deviations from the spec

Spec sections 6.2 and 6.3 describe the trigger window and trigger candle as
"highlighted". lightweight-charts 5 has no background-shading primitive on the
candlestick series, so Tasks 6 and 7 mark the trigger with a labelled arrow
marker instead of a shaded region. This preserves the information — you can
still see exactly which bar triggered — with less implementation risk than a
custom series plugin. If shading turns out to matter after seeing it on screen,
it needs a custom pane primitive and should be its own task.

Zone bands are drawn as paired boundary lines for the same reason.

The dashboard has no JavaScript test runner installed — `dashboard/package.json`
carries no vitest, jest, or testing-library dependency. Tasks 4, 6, 7, and 8
therefore verify by TypeScript compilation plus the manual checks in Task 8
Step 6, rather than by automated component tests. This was ratified as a
deliberate scope decision: the correctness logic under audit lives in Python
and is fully unit-tested there. Adding a frontend test stack is a separate
decision, not part of this plan.
