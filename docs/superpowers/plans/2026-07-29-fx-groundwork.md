# FX Groundwork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make spot FX (EUR/USD, GBP/USD) a first-class research instrument so Strategy 04 v1.1 runs on both pairs and publishes to the dashboard.

**Architecture:** Extend the IBKR data layer with a `CASH`/`IDEALPRO`/`MIDPOINT` fetch path and a resumable FX downloader; add a time-at-price (TPO) profile mode and an FX session-day boundary to the Strategy 04 indicator; add a bps-of-notional commission branch and an FX session preset to the backtest config; then run v1.1 on both pairs through the existing result-file + `publish_result_directory()` pipeline. An A/B script quantifies TPO-vs-volume divergence on equities so FX results are interpretable.

**Tech Stack:** Python 3.11+, `ibapi`, `pytest`, stdlib only (no new dependencies).

**Spec:** `docs/superpowers/specs/2026-07-29-fx-groundwork-design.md` (approved 2026-07-29).

## Global Constraints

- No new third-party dependencies; `ibapi` and stdlib only.
- Every default parameter value keeps current behaviour: `profile_weighting="volume"`, `session_day_boundary="calendar"`, `what_to_show="TRADES"`, `commission_bps_per_side=None`. No committed equity result may change.
- FX data is research-only midpoint data: downloader normalizes IBKR's `volume=-1` to `0.0` and the validation report must record `"volume": "none (midpoint data)"`.
- FX cost constants: commission 0.20 bps per side with $2.00 per-order minimum; half-spread in `slippage_bps_per_side` — EURUSD 0.5, GBPUSD 0.7.
- FX session: day boundary 17:00 ET; entries blocked 17:00–18:00 ET; no Friday entries; flat by Friday 16:45 ET.
- Test command form: `python -m pytest tests/<file>.py -v` (PowerShell, repo root).
- Commit after every green task. Never commit `data/` files (research caches are local-only).
- Tasks 1–7 are offline (TDD, no broker needed). Tasks 8–9 require a running IB Gateway and pause for the user if it is not available.

---

### Task 1: FX contract and `what_to_show` in the data layer

**Files:**
- Modify: `src/ai_trade/market_data.py` (contract helpers near line 63; `fetch_historical_bars` at line 94, hardcoded `"TRADES"` at line 126)
- Test: `tests/test_market_data_fx.py` (create)

**Interfaces:**
- Produces: `fx_contract(base: str, quote: str = "USD") -> Contract`; `fetch_historical_bars(..., what_to_show: str = "TRADES")` keyword parameter. Task 2's downloader consumes both.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_market_data_fx.py
import ai_trade.market_data as market_data
from ai_trade.market_data import OHLCVBar, fx_contract


def test_fx_contract_fields():
    contract = fx_contract("eur")
    assert contract.symbol == "EUR"
    assert contract.secType == "CASH"
    assert contract.exchange == "IDEALPRO"
    assert contract.currency == "USD"


def test_fx_contract_non_usd_quote():
    contract = fx_contract("EUR", "gbp")
    assert contract.symbol == "EUR"
    assert contract.currency == "GBP"


def test_fetch_passes_what_to_show(monkeypatch):
    captured = {}

    def fake_connect(self, host, port, client_id):
        self.connected.set()

    def fake_run(self):
        return None

    def fake_req(self, req_id, contract, end, duration, bar_size, what_to_show,
                 use_rth, format_date, keep_up_to_date, chart_options):
        captured["what_to_show"] = what_to_show
        captured["use_rth"] = use_rth
        self.bars.append(OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.1, 1.1, 1.1, -1.0))
        self.complete.set()

    monkeypatch.setattr(market_data._HistoricalDataClient, "connect", fake_connect)
    monkeypatch.setattr(market_data._HistoricalDataClient, "run", fake_run)
    monkeypatch.setattr(market_data._HistoricalDataClient, "reqHistoricalData", fake_req)
    monkeypatch.setattr(market_data._HistoricalDataClient, "isConnected", lambda self: False)

    bars = market_data.fetch_historical_bars(
        contract=fx_contract("EUR"), duration="1 D", bar_size="15 mins",
        use_rth=False, what_to_show="MIDPOINT",
    )
    assert captured["what_to_show"] == "MIDPOINT"
    assert captured["use_rth"] == 0
    assert bars[0].volume == -1.0


def test_fetch_default_what_to_show_is_trades(monkeypatch):
    captured = {}

    def fake_connect(self, host, port, client_id):
        self.connected.set()

    def fake_req(self, req_id, contract, end, duration, bar_size, what_to_show,
                 use_rth, format_date, keep_up_to_date, chart_options):
        captured["what_to_show"] = what_to_show
        self.bars.append(OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.1, 1.1, 1.1, 10.0))
        self.complete.set()

    monkeypatch.setattr(market_data._HistoricalDataClient, "connect", fake_connect)
    monkeypatch.setattr(market_data._HistoricalDataClient, "run", lambda self: None)
    monkeypatch.setattr(market_data._HistoricalDataClient, "reqHistoricalData", fake_req)
    monkeypatch.setattr(market_data._HistoricalDataClient, "isConnected", lambda self: False)

    market_data.fetch_historical_bars(
        contract=market_data.spy_contract(), duration="1 D", bar_size="15 mins",
    )
    assert captured["what_to_show"] == "TRADES"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_market_data_fx.py -v`
Expected: FAIL — `ImportError: cannot import name 'fx_contract'`

- [ ] **Step 3: Implement**

In `src/ai_trade/market_data.py`, add after `mgc_continuous_contract()` (line 91):

```python
def fx_contract(base: str, quote: str = "USD") -> Contract:
    """Return a research-only IDEALPRO spot-FX contract.

    Spot FX serves MIDPOINT bars only (no TRADES, no volume). Like the
    other contract helpers this is for read-only historical research and
    must never be passed to an order API.
    """
    contract = Contract()
    contract.symbol = base.upper()
    contract.secType = "CASH"
    contract.exchange = "IDEALPRO"
    contract.currency = quote.upper()
    return contract
```

In `fetch_historical_bars`, add the keyword parameter after `end_date_time: str = ""`:

```python
    what_to_show: str = "TRADES",
```

and replace the literal `"TRADES"` in the `reqHistoricalData` call (line 126) with `what_to_show`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_market_data_fx.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/market_data.py tests/test_market_data_fx.py
git commit -m "Add spot-FX contract and what_to_show to the IBKR data layer"
```

---

### Task 2: Resumable FX midpoint downloader

**Files:**
- Modify: `src/ai_trade/market_data.py` (`save_bars`, line 171)
- Create: `src/ai_trade/download_fx_history.py`
- Test: `tests/test_download_fx_history.py` (create)

**Interfaces:**
- Consumes: `fx_contract`, `fetch_historical_bars(..., what_to_show="MIDPOINT")` from Task 1; `merge_bars` from `ai_trade.download_v4_history`; `load_ohlcv_csv` from `ai_trade.strategy_01`.
- Produces: CSV caches `data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv` (+ `_1h`, + GBPUSD) consumed by Task 9; `normalize_midpoint_volume(bars) -> list[OHLCVBar]`; `save_bars(..., extra: dict | None = None)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_download_fx_history.py
import json

from ai_trade.download_fx_history import normalize_midpoint_volume
from ai_trade.market_data import OHLCVBar, save_bars


def _bar(timestamp: str, volume: float) -> OHLCVBar:
    return OHLCVBar(timestamp, 1.1, 1.2, 1.0, 1.15, volume)


def test_normalize_midpoint_volume_zeroes_ibkr_sentinel():
    bars = [_bar("2026-01-05T00:00:00Z", -1.0), _bar("2026-01-05T00:15:00Z", -1.0)]
    normalized = normalize_midpoint_volume(bars)
    assert [bar.volume for bar in normalized] == [0.0, 0.0]
    # Prices and timestamps are untouched.
    assert normalized[0].timestamp == "2026-01-05T00:00:00Z"
    assert normalized[0].close == 1.15


def test_save_bars_extra_lands_in_validation_report(tmp_path):
    bars = [_bar("2026-01-05T00:00:00Z", 0.0)]
    _, report_path = save_bars(
        bars, directory=tmp_path, symbol="EURUSD", timeframe="15m",
        source="ibkr_midpoint_research_only",
        extra={"volume": "none (midpoint data)"},
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["volume"] == "none (midpoint data)"
    assert report["source"] == "ibkr_midpoint_research_only"
    assert report["validation"]["valid"] is True


def test_backfill_uses_midpoint_and_normalizes(monkeypatch, tmp_path):
    import ai_trade.download_fx_history as dl

    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return [
            OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.2, 1.0, 1.15, -1.0),
            OHLCVBar("2026-01-05T00:15:00Z", 1.15, 1.2, 1.1, 1.18, -1.0),
        ]

    monkeypatch.setattr(dl, "fetch_historical_bars", fake_fetch)
    added = dl.backfill_pair_timeframe(
        pair="EURUSD", timeframe="15m", directory=tmp_path,
        target_start=dl._time("2026-01-05T00:00:00Z"),
        port=4001, client_id=700, pause_seconds=0.0,
    )
    assert added == 2
    assert calls[0]["what_to_show"] == "MIDPOINT"
    assert calls[0]["use_rth"] is False
    assert calls[0]["contract"].secType == "CASH"
    saved = (tmp_path / "eurusd_15m.csv").read_text(encoding="utf-8")
    assert ",-1.0" not in saved  # sentinel volume never persisted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_download_fx_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_trade.download_fx_history'`

- [ ] **Step 3: Implement**

In `src/ai_trade/market_data.py`, change `save_bars` signature and report:

```python
def save_bars(
    bars: Iterable[OHLCVBar], *, directory: Path, symbol: str, timeframe: str,
    source: str = "ibkr", extra: dict | None = None,
) -> tuple[Path, Path]:
```

and just before `report_path.write_text(...)`:

```python
    if extra:
        report.update(extra)
```

Create `src/ai_trade/download_fx_history.py`:

```python
"""Resumable, read-only spot-FX midpoint history caches (EURUSD, GBPUSD).

Spot FX on IDEALPRO serves MIDPOINT bars only: there is no trade volume.
IBKR reports the sentinel ``volume = -1`` on midpoint bars; this downloader
stores an explicit ``0.0`` and records ``"volume": "none (midpoint data)"``
in the validation report so no downstream reader can mistake the column for
real volume. Unlike continuous futures, ``CASH`` requests accept an end
time, so a chunked multi-year backfill is possible.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import (
    HistoricalDataError,
    OHLCVBar,
    fetch_historical_bars,
    fx_contract,
    save_bars,
)
from ai_trade.strategy_01 import load_ohlcv_csv

CHUNKS = {"15m": ("90 D", "15 mins"), "1h": ("1 Y", "1 hour")}
PAIRS = {"EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD")}


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalize_midpoint_volume(bars: list[OHLCVBar]) -> list[OHLCVBar]:
    """Replace IBKR's midpoint volume sentinel (-1) with an explicit zero."""
    return [replace(bar, volume=0.0) for bar in bars]


def backfill_pair_timeframe(
    *,
    pair: str,
    timeframe: str,
    directory: Path,
    target_start: datetime,
    port: int,
    client_id: int,
    pause_seconds: float,
) -> int:
    base, quote = PAIRS[pair]
    duration, bar_size = CHUNKS[timeframe]
    csv_path = directory / f"{pair.lower()}_{timeframe}.csv"
    cached = load_ohlcv_csv(csv_path) if csv_path.exists() else []
    before = len(cached)
    request_number = 0
    while not cached or _time(cached[0].timestamp) > target_start:
        # IBKR's UTC request form uses a dash between date and time and does
        # not append a timezone token.
        end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
        incoming = normalize_midpoint_volume(
            fetch_historical_bars(
                contract=fx_contract(base, quote), duration=duration, bar_size=bar_size,
                port=port, client_id=client_id + request_number, use_rth=False,
                timeout=90, end_date_time=end, what_to_show="MIDPOINT",
            )
        )
        merged = merge_bars(cached, incoming)
        if cached and merged[0].timestamp >= cached[0].timestamp:
            raise HistoricalDataError(
                f"{pair} {timeframe} backfill made no progress at {cached[0].timestamp}."
            )
        cached = merged
        save_bars(
            cached, directory=directory, symbol=pair, timeframe=timeframe,
            source="ibkr_midpoint_research_only",
            extra={"volume": "none (midpoint data)"},
        )
        request_number += 1
        print(f"{pair} {timeframe}: {len(cached)} cached bars; earliest {cached[0].timestamp}")
        if _time(cached[0].timestamp) <= target_start:
            break
        time.sleep(pause_seconds)
    return len(cached) - before


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill local spot-FX midpoint caches with read-only IBKR bars."
    )
    parser.add_argument("--pairs", nargs="+", choices=tuple(PAIRS), default=tuple(PAIRS))
    parser.add_argument("--timeframes", nargs="+", choices=tuple(CHUNKS), default=tuple(CHUNKS))
    parser.add_argument("--target-start", default="2021-07-29", help="UTC calendar date to reach, YYYY-MM-DD.")
    parser.add_argument("--output-root", type=Path, default=Path("data/market_data/ibkr"))
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=700)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        for pair_offset, pair in enumerate(args.pairs):
            directory = args.output_root / pair / "v1_5y"
            for tf_offset, timeframe in enumerate(args.timeframes):
                added = backfill_pair_timeframe(
                    pair=pair, timeframe=timeframe, directory=directory, target_start=target,
                    port=args.port, client_id=args.client_id + pair_offset * 60 + tf_offset * 30,
                    pause_seconds=args.pause_seconds,
                )
                print(f"{pair} {timeframe}: added {added} bars; cache retained locally at {directory}")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_download_fx_history.py tests/test_market_data_fx.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/market_data.py src/ai_trade/download_fx_history.py tests/test_download_fx_history.py
git commit -m "Add resumable spot-FX midpoint downloader with explicit zero volume"
```

---

### Task 3: TPO (time-at-price) profile weighting

**Files:**
- Modify: `src/ai_trade/strategy_04_indicator.py` (`Strategy04IndicatorParameters` at line 26, `__post_init__` at line 61, `_session_profile` at line 201, `session_volume_references` at line 239)
- Test: `tests/test_strategy_04_profile_weighting.py` (create)

**Interfaces:**
- Produces: `Strategy04IndicatorParameters.profile_weighting: str = "volume"` (allowed: `"volume"`, `"time"`); `_session_profile(rows, bins, value_area_fraction, weighting="volume")`. Tasks 6 and 7 build presets with `replace(..., profile_weighting="time")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_strategy_04_profile_weighting.py
import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    _session_profile,
)


def _bar(low: float, high: float, volume: float) -> OHLCVBar:
    return OHLCVBar("2026-01-05T14:30:00Z", low, high, low, high, volume)


def _rows(volume_low: float, volume_high: float) -> list[OHLCVBar]:
    # One bar occupies bin 0 (100.0-101.0); two bars occupy bin 9 (109.0-110.0).
    return [
        _bar(100.0, 100.9, volume_low),
        _bar(109.0, 110.0, volume_high),
        _bar(109.0, 110.0, volume_high),
    ]


def test_volume_weighting_follows_volume():
    poc, _, _ = _session_profile(_rows(volume_low=5.0, volume_high=1.0), 10, 0.7)
    assert poc == pytest.approx(100.5)


def test_time_weighting_follows_bar_count():
    poc, _, _ = _session_profile(_rows(volume_low=5.0, volume_high=1.0), 10, 0.7, weighting="time")
    assert poc == pytest.approx(109.5)


def test_zero_volume_breaks_volume_mode_but_not_time_mode():
    rows = _rows(volume_low=0.0, volume_high=0.0)
    broken_poc, _, _ = _session_profile(rows, 10, 0.7)
    assert broken_poc == pytest.approx(100.5)  # flat profile: first bin wins (the bug)
    tpo_poc, _, _ = _session_profile(rows, 10, 0.7, weighting="time")
    assert tpo_poc == pytest.approx(109.5)  # time mode: most-occupied bin wins


def test_profile_weighting_parameter_validation():
    assert Strategy04IndicatorParameters().profile_weighting == "volume"
    Strategy04IndicatorParameters(profile_weighting="time")  # allowed
    with pytest.raises(ValueError):
        Strategy04IndicatorParameters(profile_weighting="tpo")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_strategy_04_profile_weighting.py -v`
Expected: FAIL — `TypeError: _session_profile() got an unexpected keyword argument 'weighting'` and no `profile_weighting` field

- [ ] **Step 3: Implement**

In `Strategy04IndicatorParameters`, add after `volume_scoring_kinds` (line 47):

```python
    profile_weighting: str = "volume"
```

In `__post_init__`, add:

```python
        if self.profile_weighting not in {"volume", "time"}:
            raise ValueError("Profile weighting must be 'volume' or 'time'")
```

Change `_session_profile` to accept and apply the weighting (docstring updated to match):

```python
def _session_profile(
    rows: list[OHLCVBar], bins: int, value_area_fraction: float, weighting: str = "volume"
) -> tuple[float, float, float]:
    """Return a reproducible session profile of POC, VAH and VAL.

    ``volume`` weights each bar by its traded volume; ``time`` weights every
    bar equally (time-at-price), which is the only sound option for midpoint
    data that carries no volume.
    """
    session_low = min(row.low for row in rows)
    session_high = max(row.high for row in rows)
    if session_high <= session_low:
        return session_low, session_low, session_low
    step = (session_high - session_low) / bins
    profile = [0.0] * bins
    for row in rows:
        first = max(0, min(bins - 1, int((row.low - session_low) / step)))
        last = max(0, min(bins - 1, int((row.high - session_low) / step)))
        count = max(last - first + 1, 1)
        weight = 1.0 if weighting == "time" else max(row.volume, 0.0)
        allocation = weight / count
        for index in range(first, last + 1):
            profile[index] += allocation
```

Keep the POC/value-area walk (current lines 219–236, from `poc_index = max(...)` through `return center(...)`) exactly as it is today — only the signature, docstring, and the `weight`/`allocation` lines change.

In `session_volume_references` (line 254), thread the parameter through:

```python
        poc, vah, val = _session_profile(
            session_rows, params.volume_profile_bins, params.volume_value_area,
            params.profile_weighting,
        )
```

- [ ] **Step 4: Run tests to verify they pass, and prove no regression**

Run: `python -m pytest tests/test_strategy_04_profile_weighting.py tests/test_strategy_04_indicator.py -v`
Expected: all passed (existing indicator tests prove the `"volume"` default is unchanged)

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/strategy_04_indicator.py tests/test_strategy_04_profile_weighting.py
git commit -m "Add time-at-price profile weighting for volume-less instruments"
```

---

### Task 4: FX session-day boundary

**Files:**
- Modify: `src/ai_trade/strategy_04_indicator.py` (params, `__post_init__`, and the session grouping in `session_volume_references` at line 246)
- Test: `tests/test_strategy_04_session_boundary.py` (create)

**Interfaces:**
- Produces: `Strategy04IndicatorParameters.session_day_boundary: str = "calendar"` (allowed: `"calendar"`, `"fx_17et"`); `_session_date(timestamp: str, boundary: str) -> str`. Task 7's FX preset sets `session_day_boundary="fx_17et"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_strategy_04_session_boundary.py
import pytest

from ai_trade.strategy_04_indicator import Strategy04IndicatorParameters, _session_date


def test_calendar_boundary_uses_new_york_date():
    # 2026-07-26T21:00:00Z is Sunday 17:00 EDT.
    assert _session_date("2026-07-26T21:00:00Z", "calendar") == "2026-07-26"


def test_fx_boundary_rolls_at_17_et():
    # Sunday 17:00 EDT opens Monday's FX session.
    assert _session_date("2026-07-26T21:00:00Z", "fx_17et") == "2026-07-27"
    # Sunday 16:45 EDT is still Sunday's session.
    assert _session_date("2026-07-26T20:45:00Z", "fx_17et") == "2026-07-26"


def test_fx_boundary_respects_winter_offset():
    # 2026-01-05T22:00:00Z is Monday 17:00 EST (UTC-5): rolls to Tuesday.
    assert _session_date("2026-01-05T22:00:00Z", "fx_17et") == "2026-01-06"
    # 2026-01-05T21:45:00Z is Monday 16:45 EST: stays Monday.
    assert _session_date("2026-01-05T21:45:00Z", "fx_17et") == "2026-01-05"


def test_session_day_boundary_parameter_validation():
    assert Strategy04IndicatorParameters().session_day_boundary == "calendar"
    Strategy04IndicatorParameters(session_day_boundary="fx_17et")  # allowed
    with pytest.raises(ValueError):
        Strategy04IndicatorParameters(session_day_boundary="utc")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_strategy_04_session_boundary.py -v`
Expected: FAIL — `ImportError: cannot import name '_session_date'`

- [ ] **Step 3: Implement**

In `Strategy04IndicatorParameters`, add after `profile_weighting`:

```python
    session_day_boundary: str = "calendar"
```

In `__post_init__`, add:

```python
        if self.session_day_boundary not in {"calendar", "fx_17et"}:
            raise ValueError("Session day boundary must be 'calendar' or 'fx_17et'")
```

Add the helper next to `_parse`/`_format` (after line 186), reusing the module's existing `NEW_YORK` timezone constant and `timedelta` import:

```python
def _session_date(timestamp: str, boundary: str) -> str:
    """Return the session day a bar belongs to.

    ``calendar`` is the New York calendar date (equities). ``fx_17et``
    implements the 24/5 FX convention: the day rolls at 17:00 New York
    time, so a bar at or after 17:00 belongs to the next session date.
    """
    local = _parse(timestamp).astimezone(NEW_YORK)
    if boundary == "fx_17et" and local.hour >= 17:
        return (local.date() + timedelta(days=1)).isoformat()
    return local.date().isoformat()
```

In `session_volume_references`, replace the grouping line (246):

```python
        session_date = _session_date(bar.timestamp, params.session_day_boundary)
```

- [ ] **Step 4: Run tests to verify they pass, and prove no regression**

Run: `python -m pytest tests/test_strategy_04_session_boundary.py tests/test_strategy_04_indicator.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/strategy_04_indicator.py tests/test_strategy_04_session_boundary.py
git commit -m "Add 17:00 ET FX session-day boundary to the zone indicator"
```

---

### Task 5: bps-of-notional commission and the FX backtest preset

**Files:**
- Modify: `src/ai_trade/backtest_strategy_01.py` (`BacktestConfig` at line 26; cost computation at lines 186–191)
- Create: `src/ai_trade/fx_config.py`
- Test: `tests/test_fx_backtest_config.py` (create)

**Interfaces:**
- Consumes: `BacktestConfig`, `run_backtest` from `ai_trade.backtest_strategy_01`.
- Produces: `BacktestConfig.commission_bps_per_side: float | None = None` and `BacktestConfig.min_commission_per_order: float = 0.0`; `fx_backtest_config(pair: str) -> BacktestConfig` and `FX_HALF_SPREAD_BPS` in `ai_trade.fx_config`. Task 7's runner consumes `fx_backtest_config`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fx_backtest_config.py
import pytest

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest
from ai_trade.fx_config import FX_HALF_SPREAD_BPS, fx_backtest_config
from ai_trade.market_data import OHLCVBar


def _fx_bars() -> list[OHLCVBar]:
    # Monday 2026-07-27, 23:00 UTC = 19:00 EDT (inside the FX entry window).
    return [
        OHLCVBar("2026-07-27T23:00:00Z", 1.10000, 1.10050, 1.09990, 1.10020, 0.0),
        OHLCVBar("2026-07-27T23:15:00Z", 1.10020, 1.10500, 1.10010, 1.10400, 0.0),
    ]


def _signal(entry_timestamp: str) -> dict[str, object]:
    return {
        "decision_timestamp": entry_timestamp,
        "entry_timestamp": entry_timestamp,
        "side": "long",
        "jaw": 1.09800,
        "stop_reference": 1.09800,
    }


def test_fx_preset_values():
    config = fx_backtest_config("EURUSD")
    assert config.commission_bps_per_side == 0.20
    assert config.min_commission_per_order == 2.0
    assert config.slippage_bps_per_side == FX_HALF_SPREAD_BPS["EURUSD"] == 0.5
    assert fx_backtest_config("gbpusd").slippage_bps_per_side == 0.7
    assert config.block_friday_entries is True
    assert config.friday_close_time == (16, 45)
    assert config.entry_window_start == (18, 0)
    assert config.entry_window_end == (17, 0)


def test_bps_commission_with_binding_minimum():
    config = fx_backtest_config("EURUSD")
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    assert len(trades) == 1
    trade = trades[0]
    # ~75k units at ~1.10: 0.20 bps per side is ~$1.65 < $2 minimum, so
    # the $2 per-order minimum binds on both sides.
    per_side_entry = trade.entry_price * trade.quantity * 0.20 / 10_000
    assert per_side_entry < 2.0
    assert trade.costs == pytest.approx(4.0)


def test_bps_commission_without_minimum():
    config = BacktestConfig(
        commission_bps_per_side=0.20, min_commission_per_order=0.0,
        slippage_bps_per_side=0.5, entry_window_start=(18, 0), entry_window_end=(17, 0),
    )
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    trade = trades[0]
    expected = (trade.entry_price + trade.exit_price) * trade.quantity * 0.20 / 10_000
    assert trade.costs == pytest.approx(expected)


def test_per_share_commission_still_default():
    config = BacktestConfig(entry_window_start=(18, 0), entry_window_end=(17, 0))
    trades = run_backtest(_fx_bars(), [_signal("2026-07-27T23:00:00Z")], "fixed", config)
    trade = trades[0]
    assert trade.costs == pytest.approx(trade.quantity * 0.005 * 2)


def test_rollover_hour_entries_are_blocked():
    config = fx_backtest_config("EURUSD")
    # 21:15 UTC = 17:15 EDT: inside the blocked 17:00-18:00 rollover hour.
    bars = [
        OHLCVBar("2026-07-27T21:15:00Z", 1.10000, 1.10050, 1.09990, 1.10020, 0.0),
        OHLCVBar("2026-07-27T21:30:00Z", 1.10020, 1.10500, 1.10010, 1.10400, 0.0),
    ]
    assert run_backtest(bars, [_signal("2026-07-27T21:15:00Z")], "fixed", config) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fx_backtest_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_trade.fx_config'`

- [ ] **Step 3: Implement**

In `BacktestConfig` (after `commission_per_contract_per_side`, line 38):

```python
    commission_bps_per_side: float | None = None
    min_commission_per_order: float = 0.0
```

Replace the cost computation in `run_backtest` (lines 186–191):

```python
        if config.commission_bps_per_side is not None:
            # Spot FX: commission is charged in bps of traded notional with a
            # per-order minimum, on each side at that side's fill price.
            fraction = config.commission_bps_per_side / 10_000
            entry_commission = max(entry * quantity * fraction, config.min_commission_per_order)
            exit_commission = max(exit_price * quantity * fraction, config.min_commission_per_order)
            costs = entry_commission + exit_commission
        else:
            commission = (
                config.commission_per_contract_per_side
                if config.commission_per_contract_per_side is not None
                else config.commission_per_share_per_side
            )
            costs = quantity * commission * 2
```

Create `src/ai_trade/fx_config.py`:

```python
"""Research-only spot-FX backtest configuration presets.

The FX week runs Sunday 17:00 to Friday 17:00 New York time. Entries are
blocked in the 17:00-18:00 rollover hour (thin books, wide spreads, broker
maintenance) via the midnight-spanning entry window 18:00 -> 17:00. Friday
entries stay blocked and positions go flat by Friday 16:45, before the
17:00 close. Commission follows IBKR IDEALPRO tier 1 (0.20 bps of notional
per side, $2.00 per-order minimum); the half-spread of midpoint fills is
folded into ``slippage_bps_per_side`` per pair. All values are parameters
for the existing cost-stress workflow, not validated constants.
"""

from __future__ import annotations

from ai_trade.backtest_strategy_01 import BacktestConfig

FX_HALF_SPREAD_BPS = {"EURUSD": 0.5, "GBPUSD": 0.7}


def fx_backtest_config(pair: str) -> BacktestConfig:
    """Return the 24/5 spot-FX preset for one supported pair."""
    return BacktestConfig(
        slippage_bps_per_side=FX_HALF_SPREAD_BPS[pair.upper()],
        block_friday_entries=True,
        force_friday_close=True,
        friday_close_time=(16, 45),
        entry_window_start=(18, 0),
        entry_window_end=(17, 0),
        commission_bps_per_side=0.20,
        min_commission_per_order=2.0,
    )
```

- [ ] **Step 4: Run tests to verify they pass, and prove no regression**

Run: `python -m pytest tests/test_fx_backtest_config.py tests/test_backtest_strategy_01.py -v`
Expected: all passed (existing backtest tests prove the default cost path is unchanged)

- [ ] **Step 5: Commit**

```bash
git add src/ai_trade/backtest_strategy_01.py src/ai_trade/fx_config.py tests/test_fx_backtest_config.py
git commit -m "Add bps-of-notional commission branch and spot-FX session preset"
```

---

### Task 6: TPO-vs-volume A/B bridge report on equities

**Files:**
- Create: `src/ai_trade/compare_profile_weighting.py`
- Test: `tests/test_compare_profile_weighting.py` (create)

**Interfaces:**
- Consumes: `build_one_hour_indicator`, `strategy_04_v0_3_parameters` from `ai_trade.strategy_04_indicator`; `candidate_signals_v1_1`, `Strategy04V11ExecutionParameters` from `ai_trade.strategy_04_v1_1`; `load_ohlcv_csv` from `ai_trade.strategy_01`; `replace` from `dataclasses`.
- Produces: `compare_symbol(fifteen, hours) -> dict` (pure, unit-testable) and a CLI writing `strategies/strategy_04/analysis/tpo_vs_volume/report.json` + `REPORT.md`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compare_profile_weighting.py
from datetime import datetime, timedelta, timezone

from ai_trade.compare_profile_weighting import compare_symbol
from ai_trade.market_data import OHLCVBar


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uniform_bars(count: int, minutes: int) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return [
        OHLCVBar(_stamp(start + timedelta(minutes=minutes * i)),
                 100 + (i % 5) * 0.2, 100.6 + (i % 5) * 0.2,
                 99.8 + (i % 5) * 0.2, 100.3 + (i % 5) * 0.2, 1_000.0)
        for i in range(count)
    ]


def test_uniform_volume_gives_identical_results():
    # When every bar carries identical volume, volume weighting and time
    # weighting distribute identically, so zones and signals must match.
    hours = _uniform_bars(200, 60)
    fifteen = _uniform_bars(800, 15)
    result = compare_symbol(fifteen, hours)
    assert result["qualified_zones"]["volume"] == result["qualified_zones"]["time"]
    assert result["qualified_zones"]["shared"] == result["qualified_zones"]["volume"]
    assert result["signals"]["volume_only"] == 0
    assert result["signals"]["time_only"] == 0


def test_report_shape():
    hours = _uniform_bars(200, 60)
    fifteen = _uniform_bars(800, 15)
    result = compare_symbol(fifteen, hours)
    for key in ("qualified_zones", "signals"):
        assert key in result
    assert set(result["qualified_zones"]) >= {"volume", "time", "shared"}
    assert set(result["signals"]) >= {"volume", "time", "shared", "volume_only", "time_only"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compare_profile_weighting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_trade.compare_profile_weighting'`

- [ ] **Step 3: Implement**

Create `src/ai_trade/compare_profile_weighting.py`:

```python
"""Measure how time-at-price weighting changes v0.3 zones and v1.1 signals.

This is the bridge report required before any volume-less instrument (spot
FX) result can be interpreted: it quantifies, on SPY/QQQ/DIA where real
volume exists, how far TPO weighting diverges from the volume weighting
that every committed equity result used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import build_one_hour_indicator, strategy_04_v0_3_parameters
from ai_trade.strategy_04_v1_1 import Strategy04V11ExecutionParameters, candidate_signals_v1_1

DATA = {
    "SPY": ("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
    "QQQ": ("data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "data/market_data/ibkr/QQQ/v5_5y/qqq_1h.csv"),
    "DIA": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "data/market_data/ibkr/US30_DIA/v5_5y/dia_1h.csv"),
}


def _qualified_zone_keys(events) -> set[tuple[str, str, float, float]]:
    """Identify qualified zones by observable geometry, not zone_id.

    Zone ids are assigned in creation order and may differ between runs
    whose zone populations diverge; timestamp, side, and boundaries are
    the stable identity of a qualification event.
    """
    return {
        (event.timestamp, event.side, event.lower, event.upper)
        for event in events
        if event.event == "qualified"
    }


def _signal_keys(signals: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {(str(signal["decision_timestamp"]), str(signal["side"])) for signal in signals}


def compare_symbol(fifteen: Iterable[OHLCVBar], hours: Iterable[OHLCVBar]) -> dict[str, object]:
    """Run the v0.3 indicator + v1.1 signals under both weightings and diff."""
    fifteen = list(fifteen)
    hours = list(hours)
    execution = Strategy04V11ExecutionParameters()
    results = {}
    for weighting in ("volume", "time"):
        params = replace(strategy_04_v0_3_parameters(), profile_weighting=weighting)
        signal_result = candidate_signals_v1_1(fifteen, hours, execution, params)
        results[weighting] = {
            "zones": _qualified_zone_keys(signal_result.indicator.events),
            "signals": _signal_keys(signal_result.signals),
        }
    volume_zones, time_zones = results["volume"]["zones"], results["time"]["zones"]
    volume_signals, time_signals = results["volume"]["signals"], results["time"]["signals"]
    return {
        "qualified_zones": {
            "volume": len(volume_zones),
            "time": len(time_zones),
            "shared": len(volume_zones & time_zones),
            "volume_only": len(volume_zones - time_zones),
            "time_only": len(time_zones - volume_zones),
        },
        "signals": {
            "volume": len(volume_signals),
            "time": len(time_signals),
            "shared": len(volume_signals & time_signals),
            "volume_only": len(volume_signals - time_signals),
            "time_only": len(time_signals - volume_signals),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare TPO vs volume profile weighting on cached equities.")
    parser.add_argument("--symbols", nargs="+", choices=tuple(DATA), default=tuple(DATA))
    parser.add_argument("--output", type=Path, default=Path("strategies/strategy_04/analysis/tpo_vs_volume"))
    args = parser.parse_args()

    report: dict[str, object] = {}
    for symbol in args.symbols:
        fifteen_path, hours_path = DATA[symbol]
        result = compare_symbol(load_ohlcv_csv(Path(fifteen_path)), load_ohlcv_csv(Path(hours_path)))
        report[symbol] = result
        print(f"{symbol}: {json.dumps(result)}")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# TPO vs volume profile weighting - equity bridge report",
        "",
        "How far time-at-price weighting diverges from volume weighting on the",
        "symbols where both exist. Read this before interpreting any spot-FX",
        "run: FX zones are TPO-qualified, and this table is the only measured",
        "link between TPO behaviour and the volume-weighted equity results.",
        "",
        "| Symbol | Zones (vol) | Zones (time) | Shared | Signals (vol) | Signals (time) | Shared |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for symbol, result in report.items():
        zones, signals = result["qualified_zones"], result["signals"]
        lines.append(
            f"| {symbol} | {zones['volume']} | {zones['time']} | {zones['shared']} "
            f"| {signals['volume']} | {signals['time']} | {signals['shared']} |"
        )
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved TPO bridge report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compare_profile_weighting.py -v`
Expected: 2 passed

- [ ] **Step 5: Generate the real bridge report from cached equity data**

Run: `python -m ai_trade.compare_profile_weighting`
Expected: one line per symbol plus `Saved TPO bridge report to strategies\strategy_04\analysis\tpo_vs_volume`. Sanity-check: shared zone counts should be a large fraction of both totals; if `shared` is near zero for every symbol, stop and investigate before proceeding.

- [ ] **Step 6: Commit**

```bash
git add src/ai_trade/compare_profile_weighting.py tests/test_compare_profile_weighting.py strategies/strategy_04/analysis/tpo_vs_volume/
git commit -m "Measure TPO-vs-volume zone and signal divergence on equities"
```

---

### Task 7: Strategy 04 v1.1 FX runner

**Files:**
- Create: `src/ai_trade/backtest_strategy_04_v1_1_fx.py`
- Test: `tests/test_backtest_strategy_04_v1_1_fx.py` (create)

**Interfaces:**
- Consumes: `fx_backtest_config` (Task 5); `profile_weighting`/`session_day_boundary` params (Tasks 3–4); `candidate_signals_v1_1`, `Strategy04V11ExecutionParameters` from `ai_trade.strategy_04_v1_1`; `run_backtest`, `summarize`, `write_results`, `_entry_allowed` from `ai_trade.backtest_strategy_01`; `_write_signals` from `ai_trade.backtest_strategy_04_v1`; `run_backtest_five_loss_reset`, `FIVE_LOSS_TIERS` from `ai_trade.rrms_five_loss_reset`; `ledger_statistics` from `ai_trade.trade_statistics`; `publish_result_directory` from `ai_trade.publish_run`.
- Produces: CLI `python -m ai_trade.backtest_strategy_04_v1_1_fx --pair EURUSD ...` writing the standard result-file set consumed by the dashboard pipeline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backtest_strategy_04_v1_1_fx.py
import json
import sys
from datetime import datetime, timedelta, timezone

from ai_trade.backtest_strategy_04_v1_1_fx import main
from ai_trade.market_data import OHLCVBar, save_bars


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_fixture(directory) -> tuple[str, str]:
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    hours = [
        OHLCVBar(_stamp(start + timedelta(hours=i)),
                 1.10 + (i % 7) * 0.001, 1.102 + (i % 7) * 0.001,
                 1.098 + (i % 7) * 0.001, 1.101 + (i % 7) * 0.001, 0.0)
        for i in range(120)
    ]
    fifteen = [
        OHLCVBar(_stamp(start + timedelta(minutes=15 * i)),
                 1.10 + (i % 11) * 0.0004, 1.1015 + (i % 11) * 0.0004,
                 1.0985 + (i % 11) * 0.0004, 1.1005 + (i % 11) * 0.0004, 0.0)
        for i in range(480)
    ]
    save_bars(hours, directory=directory, symbol="EURUSD", timeframe="1h",
              source="test", extra={"volume": "none (midpoint data)"})
    save_bars(fifteen, directory=directory, symbol="EURUSD", timeframe="15m",
              source="test", extra={"volume": "none (midpoint data)"})
    return str(directory / "eurusd_15m.csv"), str(directory / "eurusd_1h.csv")


def test_fx_runner_writes_contract_files(tmp_path, monkeypatch):
    fifteen, hours = _write_fixture(tmp_path / "cache")
    output = tmp_path / "results"
    monkeypatch.setattr(sys, "argv", [
        "backtest_strategy_04_v1_1_fx", "--pair", "EURUSD",
        "--fifteen-minute", fifteen, "--one-hour", hours,
        "--output", str(output), "--skip-publish",
    ])
    assert main() == 0
    for name in ("candidate_signals.csv", "fixed_trades.csv", "fixed_summary.json",
                 "rrms_trades.csv", "rrms_summary.json", "backtest_report.json"):
        assert (output / name).is_file(), name

    report = json.loads((output / "backtest_report.json").read_text(encoding="utf-8"))
    assert report["strategy_id"] == "strategy_04_v1_1_shallow_long_penetration"
    assert report["symbol"] == "EURUSD"
    assert report["market"] == "spot_fx_midpoint"
    assert report["indicator_parameters"]["profile_weighting"] == "time"
    assert report["indicator_parameters"]["session_day_boundary"] == "fx_17et"
    assert report["backtest_configuration"]["commission_bps_per_side"] == 0.20
    assert "TPO" in report["warning"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_strategy_04_v1_1_fx.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ai_trade.backtest_strategy_04_v1_1_fx'`

- [ ] **Step 3: Implement**

Create `src/ai_trade/backtest_strategy_04_v1_1_fx.py` (mirrors `backtest_strategy_04_v1_1_asset.py`, lines 22–105, with the FX config, TPO/FX indicator preset, and publish step):

```python
"""Run Strategy 04 v1.1 on cached spot-FX midpoint data (EURUSD, GBPUSD)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from ai_trade.backtest_strategy_01 import _entry_allowed, run_backtest, summarize, write_results
from ai_trade.backtest_strategy_04_v1 import _write_signals
from ai_trade.fx_config import fx_backtest_config
from ai_trade.publish_run import publish_result_directory
from ai_trade.rrms_five_loss_reset import FIVE_LOSS_TIERS, run_backtest_five_loss_reset
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters
from ai_trade.strategy_04_v1_1 import (
    Strategy04V11ExecutionParameters,
    candidate_signals_v1_1,
)
from ai_trade.trade_statistics import ledger_statistics

WARNING = (
    "Historical research only. Spot-FX midpoint data: zones are TPO-qualified "
    "(time-at-price, no volume exists), fills assume a fixed modelled half-spread, "
    "and commission is IBKR IDEALPRO tier-1 bps of notional. Read the TPO-vs-volume "
    "bridge report (strategies/strategy_04/analysis/tpo_vs_volume) before comparing "
    "against any equity result."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Strategy 04 v1.1 on cached spot-FX data.")
    parser.add_argument("--pair", required=True, choices=("EURUSD", "GBPUSD"))
    parser.add_argument("--fifteen-minute", required=True, type=Path)
    parser.add_argument("--one-hour", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    fifteen = load_ohlcv_csv(args.fifteen_minute)
    hours = load_ohlcv_csv(args.one_hour)
    execution_params = Strategy04V11ExecutionParameters()
    indicator_params = replace(
        strategy_04_v0_3_parameters(),
        profile_weighting="time",
        session_day_boundary="fx_17et",
    )
    signal_result = candidate_signals_v1_1(fifteen, hours, execution_params, indicator_params)
    signals = signal_result.signals
    config = fx_backtest_config(args.pair)

    args.output.mkdir(parents=True, exist_ok=True)
    _write_signals(args.output / "candidate_signals.csv", signals)
    fixed_trades = run_backtest(fifteen, signals, "fixed", config)
    rrms_trades = run_backtest_five_loss_reset(fifteen, signals, config)
    fixed_summary = summarize(fixed_trades, config.starting_equity)
    rrms_summary = summarize(rrms_trades, config.starting_equity)
    write_results(fixed_trades, fixed_summary, "fixed", args.output)
    write_results(rrms_trades, rrms_summary, "rrms", args.output)

    fixed_detail = ledger_statistics(args.output / "fixed_trades.csv")
    rrms_detail = ledger_statistics(args.output / "rrms_trades.csv")
    eligible = [
        signal for signal in signals
        if _entry_allowed(str(signal["entry_timestamp"]), str(signal["side"]), config)
    ]
    report = {
        "strategy_id": "strategy_04_v1_1_shallow_long_penetration",
        "mode": "historical_backtest_only",
        "market": "spot_fx_midpoint",
        "symbol": args.pair.upper(),
        "data": {
            "fifteen_minute_file": str(args.fifteen_minute),
            "fifteen_minute_bar_count": len(fifteen),
            "fifteen_minute_first": fifteen[0].timestamp,
            "fifteen_minute_last": fifteen[-1].timestamp,
            "one_hour_file": str(args.one_hour),
            "one_hour_bar_count": len(hours),
            "one_hour_first": hours[0].timestamp,
            "one_hour_last": hours[-1].timestamp,
        },
        "indicator_version": "0.3",
        "indicator_parameters": asdict(indicator_params),
        "indicator_summary": signal_result.indicator.summary,
        "execution_parameters": asdict(execution_params),
        "backtest_configuration": {
            **asdict(config),
            "rrms_tiers": list(FIVE_LOSS_TIERS),
            "rrms_reset": "after profit or after the fifth consecutive negative exit",
        },
        "change_from_v1": (
            "Long trigger low may penetrate no more than 25% of demand-zone width. "
            "Shorts and every other rule are unchanged."
        ),
        "candidate_signal_count": len(signals),
        "session_eligible_signal_count": len(eligible),
        "results": {
            "fixed": {**fixed_summary, "details": fixed_detail},
            "rrms": {**rrms_summary, "details": rrms_detail},
        },
        "warning": WARNING,
    }
    (args.output / "backtest_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["results"], indent=2))
    print(f"Saved {args.pair} Strategy 04 v1.1 FX backtest to {args.output}")

    if not args.skip_publish:
        bundle_dir = publish_result_directory(args.output)
        print(f"Published visualization bundle to {bundle_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backtest_strategy_04_v1_1_fx.py -v`
Expected: 1 passed (the fixture may yield zero signals — the contract files must exist regardless)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests -v`
Expected: all passed, no existing test broken

- [ ] **Step 6: Commit**

```bash
git add src/ai_trade/backtest_strategy_04_v1_1_fx.py tests/test_backtest_strategy_04_v1_1_fx.py
git commit -m "Add Strategy 04 v1.1 runner for spot-FX midpoint caches"
```

---

### Task 8: Download 5 years of EURUSD and GBPUSD (requires IB Gateway)

**Environment gate:** This task talks to a live IB Gateway on port 4001. If the gateway is not running, STOP and ask the user to start it before continuing.

**Files:**
- Creates (local only, never committed): `data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv`, `eurusd_1h.csv`, `data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv`, `gbpusd_1h.csv` + validation JSONs.

- [ ] **Step 1: Run the backfill (resumable; re-run the same command if it stalls)**

Run: `python -m ai_trade.download_fx_history --target-start 2021-07-29`
Expected: repeated `EURUSD 15m: N cached bars; earliest ...` lines walking backwards to 2021-07-29, then the same for 1h and for GBPUSD. This makes ~20 paced requests per pair for 15m data and may take a while.

- [ ] **Step 2: Verify the caches**

Run: `python -c "import json,glob; [print(p, json.load(open(p))['validation']['valid'], json.load(open(p))['volume']) for p in glob.glob('data/market_data/ibkr/*USD/v1_5y/*.validation.json')]"`
Expected: four lines, each ending `True none (midpoint data)`. If any is `False`, inspect that file's `validation` block and re-run the backfill before proceeding.

- [ ] **Step 3: Confirm nothing under `data/` is staged**

Run: `git status --short`
Expected: no `data/` entries (the cache directory is ignored). Nothing to commit for this task.

---

### Task 9: v1.1 baseline runs on both pairs, published to the dashboard

**Files:**
- Create (committed results): `strategies/strategy_04/v1_1/results/eurusd_1h_15m/` and `strategies/strategy_04/v1_1/results/gbpusd_1h_15m/` (standard contract file set each)

**Interfaces:**
- Consumes: Task 7's runner, Task 8's caches, existing `publish_result_directory` pipeline.

- [ ] **Step 1: Run EURUSD**

Run:
```bash
python -m ai_trade.backtest_strategy_04_v1_1_fx --pair EURUSD --fifteen-minute data/market_data/ibkr/EURUSD/v1_5y/eurusd_15m.csv --one-hour data/market_data/ibkr/EURUSD/v1_5y/eurusd_1h.csv --output strategies/strategy_04/v1_1/results/eurusd_1h_15m
```
Expected: fixed/rrms summary JSON printed, then `Published visualization bundle to ...`.

- [ ] **Step 2: Run GBPUSD**

Run:
```bash
python -m ai_trade.backtest_strategy_04_v1_1_fx --pair GBPUSD --fifteen-minute data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_15m.csv --one-hour data/market_data/ibkr/GBPUSD/v1_5y/gbpusd_1h.csv --output strategies/strategy_04/v1_1/results/gbpusd_1h_15m
```
Expected: same shape of output.

- [ ] **Step 3: Sanity-check the reports**

Run: `python -c "import json; [print(p, json.load(open(f'strategies/strategy_04/v1_1/results/{p}_1h_15m/backtest_report.json'))['candidate_signal_count']) for p in ('eurusd','gbpusd')]"`
Expected: a non-zero candidate signal count for each pair. Zero signals over five years means something upstream is wrong (zone qualification or session mapping) — stop and investigate, do not commit.

- [ ] **Step 4: Verify both runs appear in the dashboard**

Start the dashboard dev server (the `dashboard` configuration in `.claude/launch.json`: `npm run dev --prefix dashboard`, port 5173) and confirm both FX runs are listed in the catalog with their ledger-audit status shown. A screenshot or the catalog JSON is the proof.

- [ ] **Step 5: Commit**

```bash
git add strategies/strategy_04/v1_1/results/eurusd_1h_15m strategies/strategy_04/v1_1/results/gbpusd_1h_15m
git commit -m "Add Strategy 04 v1.1 baseline runs on EURUSD and GBPUSD midpoint data"
```

---

## Completion checklist (from the spec's "done" definition)

- [ ] FX data fetched: 5y of 15m + 1h for both pairs, validation reports clean
- [ ] TPO profile mode + FX session boundary in the indicator, defaults unchanged
- [ ] FX session + bps-commission preset in the backtest config, defaults unchanged
- [ ] TPO-vs-volume bridge report committed for SPY/QQQ/DIA
- [ ] v1.1 baseline runs on EURUSD and GBPUSD committed and visible in the dashboard
- [ ] Full test suite green
