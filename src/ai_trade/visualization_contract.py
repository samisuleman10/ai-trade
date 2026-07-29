"""Visualization bundle contract: models, validation, and atomic publication.

This is the shared exporter described in
``docs/design/strategy_visualization/shared/architecture_and_data_contract.md``.
It turns already-computed backtest results (typed trade rows and a summary
dict) into the canonical trade-ledger and performance-series datasets, then
publishes them as a self-describing bundle: sidecar JSON files plus a
``manifest.json`` that is written last and atomically, so a half-written
bundle is never mistaken for a complete one.

Nothing here recomputes strategy logic. ``build_trade_ledger`` reshapes
recorded CSV-string rows into typed JSON. ``build_performance`` reshapes
each trade's recorded ``equity_after`` into an equity/drawdown point
series and cross-checks the result against the producer's own summary --
disagreement is a bug report, not a value to silently accept.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

SCHEMA_VERSION = "1.0.0"

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RECONCILIATION_TOLERANCE = 1e-6
BUNDLE_DIRNAME = "visualization"
DATA_SUBDIR = "data"
MANIFEST_FILENAME = "manifest.json"

_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:")


class ContractError(Exception):
    """Raised when producer data or a bundle violates the contract."""


@dataclass
class Dataset:
    """One canonical sidecar plus the metadata needed to publish it."""

    dataset_id: str
    kind: str
    path: str
    payload: Dict[str, Any]
    record_count: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]


def _trade_id(run_id: str, variant: str, ordinal: int) -> str:
    return f"{run_id}:{variant}:{ordinal:06d}"


def _row_str(row: Mapping[str, Any], field: str, index: int) -> str:
    try:
        return row[field]
    except KeyError as exc:
        raise ContractError(f"row {index}: missing required field {field!r}") from exc


def _row_int(row: Mapping[str, Any], field: str, index: int) -> int:
    try:
        raw = row[field]
    except KeyError as exc:
        raise ContractError(f"row {index}: missing required field {field!r}") from exc
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"row {index}: field {field!r} is not a valid integer: {raw!r}") from exc


def _row_float(row: Mapping[str, Any], field: str, index: int) -> float:
    try:
        raw = row[field]
    except KeyError as exc:
        raise ContractError(f"row {index}: missing required field {field!r}") from exc
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"row {index}: field {field!r} is not a valid number: {raw!r}") from exc
    if not math.isfinite(value):
        raise ContractError(f"row {index}: field {field!r} must be finite, got {raw!r}")
    return value


def build_trade_ledger(rows: Sequence[Mapping[str, Any]], variant: str, run_id: str) -> Dataset:
    """Convert recorded CSV-string trade rows into a canonical trade ledger.

    Every numeric CSV field becomes a JSON number (``quantity`` and
    ``rrms_tier`` become integers, the rest become floats). Every trade
    gets a deterministic ``trade_id`` of
    ``<run_id>:<variant>:<six-digit one-based ordinal>`` and
    ``status: "closed"``, since backtest ledgers only ever contain closed
    trades. Bounds come from the first and last recorded
    ``decision_timestamp``.
    """

    trades: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        trades.append(
            {
                "trade_id": _trade_id(run_id, variant, index),
                "status": "closed",
                "decision_timestamp": _row_str(row, "decision_timestamp", index),
                "entry_timestamp": _row_str(row, "entry_timestamp", index),
                "exit_timestamp": _row_str(row, "exit_timestamp", index),
                "side": _row_str(row, "side", index),
                "rrms_tier": _row_int(row, "rrms_tier", index),
                "quantity": _row_int(row, "quantity", index),
                "entry_price": _row_float(row, "entry_price", index),
                "stop_price": _row_float(row, "stop_price", index),
                "target_price": _row_float(row, "target_price", index),
                "exit_price": _row_float(row, "exit_price", index),
                "exit_reason": _row_str(row, "exit_reason", index),
                "gross_pnl": _row_float(row, "gross_pnl", index),
                "costs": _row_float(row, "costs", index),
                "net_pnl": _row_float(row, "net_pnl", index),
                "result_r": _row_float(row, "result_r", index),
                "equity_after": _row_float(row, "equity_after", index),
            }
        )

    dataset_id = f"trades_{variant}"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "kind": "trades",
        "variant": variant,
        "trades": trades,
    }
    return Dataset(
        dataset_id=dataset_id,
        kind="trades",
        path=f"{DATA_SUBDIR}/trades-{variant}.json",
        payload=payload,
        record_count=len(rows),
        first_timestamp=rows[0]["decision_timestamp"] if rows else None,
        last_timestamp=rows[-1]["decision_timestamp"] if rows else None,
    )


def build_performance(
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    variant: str,
    starting_equity: float,
) -> Dataset:
    """Reshape recorded ``equity_after`` values into an equity/drawdown series.

    This does not recompute strategy P&L. It anchors an initial point at
    ``starting_equity`` on the first trade's ``decision_timestamp``, then
    adds one point per trade at its ``exit_timestamp`` carrying the
    running ``equity``, ``peak_equity``, ``drawdown`` and
    ``drawdown_percent``. ``trade_id`` cannot be reproduced here (this
    function has no ``run_id``), so it is always ``None``; callers that
    need ledger-matching IDs get them from ``build_trade_ledger``.

    The derived series is cross-checked against the producer's own
    ``summary``: a ``trade_count`` or ``ending_equity`` disagreement means
    the summary and the ledger describe different runs, which is rejected
    rather than silently trusted. A summary with no ``ending_equity`` at
    all is rejected too -- the guard used to skip itself when the value it
    reconciles against was absent, so the least trustworthy summaries were
    exactly the ones that went unchecked.
    """

    trade_count = summary.get("trade_count")
    if trade_count != len(rows):
        raise ContractError(
            f"summary trade_count {trade_count!r} disagrees with {len(rows)} ledger rows"
        )

    starting_equity = float(starting_equity)
    points: List[Dict[str, Any]] = [
        {
            "timestamp": rows[0]["decision_timestamp"] if rows else None,
            "trade_id": None,
            "equity": starting_equity,
            "peak_equity": starting_equity,
            "drawdown": 0.0,
            "drawdown_percent": 0.0,
        }
    ]

    equity = starting_equity
    peak_equity = starting_equity
    for index, row in enumerate(rows, start=1):
        equity = _row_float(row, "equity_after", index)
        peak_equity = max(peak_equity, equity)
        drawdown = peak_equity - equity
        drawdown_percent = (drawdown / peak_equity) if peak_equity else 0.0
        points.append(
            {
                "timestamp": _row_str(row, "exit_timestamp", index),
                "trade_id": None,
                "equity": equity,
                "peak_equity": peak_equity,
                "drawdown": drawdown,
                "drawdown_percent": drawdown_percent,
            }
        )

    ending_equity = summary.get("ending_equity")
    if ending_equity is None:
        raise ContractError("summary has no 'ending_equity' to reconcile the ledger against")
    try:
        ending_equity = float(ending_equity)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"summary 'ending_equity' is not a number: {ending_equity!r}") from exc
    if abs(equity - ending_equity) > RECONCILIATION_TOLERANCE:
        raise ContractError(
            f"summary ending_equity {ending_equity!r} disagrees with final ledger equity {equity!r}"
        )

    dataset_id = f"performance_{variant}"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "kind": "performance",
        "variant": variant,
        "summary": dict(summary),
        "points": points,
    }
    return Dataset(
        dataset_id=dataset_id,
        kind="performance",
        path=f"{DATA_SUBDIR}/performance-{variant}.json",
        payload=payload,
        record_count=len(points),
        first_timestamp=points[0]["timestamp"],
        last_timestamp=points[-1]["timestamp"],
    )


def _zone_payload(zone: Mapping[str, Any], trade_id: str) -> Dict[str, Any]:
    try:
        lower = float(zone["lower"])
        upper = float(zone["upper"])
        zone_id = int(zone["zone_id"])
        side = str(zone["side"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractError(f"trade {trade_id}: malformed zone: {exc}") from exc
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ContractError(f"trade {trade_id}: zone bounds must be finite")
    if upper < lower:
        raise ContractError(f"trade {trade_id}: zone upper {upper} is below lower {lower}")
    return {
        "zone_id": zone_id,
        "side": side,
        "lower": lower,
        "upper": upper,
        "qualified_timestamp": str(zone.get("qualified_timestamp") or ""),
        "score": int(zone.get("score") or 0),
    }


def build_zones(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """One-hour zone geometry per trade, including the zones it outranked.

    Competing zones are part of the payload, not decoration: the strategy
    ranks overlapping zones by evidence score, and a view drawing only the
    winner could never show whether the ranking picked correctly.
    """

    seen = set()
    trades: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        if trade_id in seen:
            raise ContractError(f"duplicate trade_id in zones dataset: {trade_id!r}")
        seen.add(trade_id)

        selected = entry.get("selected")
        if not isinstance(selected, Mapping):
            raise ContractError(f"trade {trade_id}: zones entry has no 'selected' zone")

        trades.append(
            {
                "trade_id": trade_id,
                "selected": _zone_payload(selected, trade_id),
                "competing": [
                    _zone_payload(zone, trade_id) for zone in (entry.get("competing") or [])
                ],
            }
        )

    return Dataset(
        dataset_id="zones",
        kind="zones",
        path=f"{DATA_SUBDIR}/zones.json",
        payload={
            "schema_version": SCHEMA_VERSION,
            "dataset_id": "zones",
            "kind": "zones",
            "trades": trades,
        },
        record_count=len(trades),
        first_timestamp=None,
        last_timestamp=None,
    )


def build_trade_audit(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """Per-trade rule-check results.

    ``passed`` is derived here from the checks rather than copied from the
    producer, so a summary can never disagree with the evidence beneath it.
    """

    seen = set()
    trades: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        if trade_id in seen:
            raise ContractError(f"duplicate trade_id in trade_audit dataset: {trade_id!r}")
        seen.add(trade_id)

        raw_checks = list(entry.get("checks") or [])
        if not raw_checks:
            raise ContractError(f"trade {trade_id}: audit entry has no checks")

        checks: List[Dict[str, Any]] = []
        for check in raw_checks:
            try:
                checks.append(
                    {
                        "check_id": str(check["check_id"]),
                        "passed": bool(check["passed"]),
                        "expected": str(check.get("expected", "")),
                        "actual": str(check.get("actual", "")),
                    }
                )
            except (KeyError, TypeError) as exc:
                raise ContractError(f"trade {trade_id}: malformed check: {exc}") from exc

        trades.append(
            {
                "trade_id": trade_id,
                "trigger_timestamp": str(entry.get("trigger_timestamp") or ""),
                "passed": all(check["passed"] for check in checks),
                "checks": checks,
            }
        )

    return Dataset(
        dataset_id="trade_audit",
        kind="trade_audit",
        path=f"{DATA_SUBDIR}/trade-audit.json",
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


def _opt(container: Any, *keys: str) -> Any:
    """Walk a nested mapping, returning None the moment a key is missing."""

    current = container
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def build_run_summary(report: Mapping[str, Any]) -> Dataset:
    """Run metadata the dashboard would otherwise have to hardcode.

    Everything here comes from ``backtest_report.json``: starting equity,
    signal funnel counts, bar counts, data range, the cost model, and each
    sizing variant's detail block.

    Absent values stay ``None`` and the cost model carries an explicit
    ``recorded`` flag. Only six of the fifty-six reports in this repo record
    a ``backtest_configuration`` at all, so substituting a default would let
    a comparison claim two runs share a cost model when one never stated one.
    """

    config = report.get("backtest_configuration")
    has_config = isinstance(config, Mapping)

    variants: Dict[str, Any] = {}
    results = report.get("results")
    if isinstance(results, Mapping):
        for name, block in results.items():
            details = _opt(block, "details")
            if isinstance(details, Mapping):
                variants[str(name)] = dict(details)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "run_summary",
        "kind": "run_summary",
        "starting_equity": _opt(config, "starting_equity") if has_config else None,
        "signals": {
            "candidate": report.get("candidate_signal_count"),
            "eligible": report.get("session_eligible_signal_count"),
        },
        "cost_model": {
            "recorded": bool(has_config),
            "slippage_bps_per_side": _opt(config, "slippage_bps_per_side") if has_config else None,
            "commission_per_share_per_side": (
                _opt(config, "commission_per_share_per_side") if has_config else None
            ),
        },
        "data": {
            "setup_bar_count": _opt(report, "data", "one_hour_bar_count"),
            "execution_bar_count": _opt(report, "data", "fifteen_minute_bar_count"),
            "first_timestamp": _opt(report, "data", "fifteen_minute_first"),
            "last_timestamp": _opt(report, "data", "fifteen_minute_last"),
        },
        "variants": variants,
    }

    return Dataset(
        dataset_id="run_summary",
        kind="run_summary",
        path=f"{DATA_SUBDIR}/run-summary.json",
        payload=payload,
        record_count=len(variants),
        first_timestamp=payload["data"]["first_timestamp"],
        last_timestamp=payload["data"]["last_timestamp"],
    )


def _validate_window(
    bars: Sequence[Mapping[str, Any]], trade_id: str, label: str
) -> List[Dict[str, Any]]:
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
        body_low = min(values["open"], values["close"])
        body_high = max(values["open"], values["close"])
        if values["low"] > body_low or body_high > values["high"]:
            raise ContractError(
                f"trade {trade_id}: {label} bar at {timestamp} violates low <= open,close <= high"
            )
        normalized.append(
            {"timestamp": timestamp, **values, "volume": _row_float(bar, "volume", index)}
        )
    return normalized


def build_audit_windows(entries: Sequence[Mapping[str, Any]]) -> Dataset:
    """Bounded bar windows around each audited trade.

    Deliberately not a full candle series. The audit view shows roughly forty
    bars per trade, and a full 15-minute series for one symbol is over 34,000
    bars -- publishing it whole would ship two megabytes to render forty.
    """

    seen = set()
    trades: List[Dict[str, Any]] = []
    stamps: List[str] = []
    for index, entry in enumerate(entries):
        trade_id = _row_str(entry, "trade_id", index)
        if trade_id in seen:
            raise ContractError(f"duplicate trade_id in audit_windows dataset: {trade_id!r}")
        seen.add(trade_id)

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
        path=f"{DATA_SUBDIR}/audit-windows.json",
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


def _validate_relative_path(path: Any) -> str:
    """Reject anything but a clean relative path within the bundle.

    Rejects empty/non-string paths, drive letters (``C:\\...`` or
    ``C:foo``), absolute paths (leading ``/`` or ``\\``, including UNC
    paths, which normalize to a leading ``//``), and any ``..`` segment.
    Both ``/`` and ``\\`` separators are checked, since this runs on
    Windows.
    """

    if not isinstance(path, str) or not path:
        raise ContractError(f"dataset path must be a non-empty string, got {path!r}")
    if _DRIVE_LETTER_RE.match(path):
        raise ContractError(f"dataset path must not contain a drive letter: {path!r}")
    normalized = path.replace("\\", "/")
    if normalized.startswith("/"):
        raise ContractError(f"dataset path must not be absolute: {path!r}")
    segments = normalized.split("/")
    if ".." in segments:
        raise ContractError(f"dataset path must not escape the bundle directory: {path!r}")
    if any(segment == "" for segment in segments):
        raise ContractError(f"dataset path must not contain empty segments: {path!r}")
    return normalized


def _write_text_atomically(path: Path, serialized: str, prefix: str) -> None:
    """Write ``serialized`` to ``path`` via temp file + ``os.replace``.

    ``os.replace`` is atomic on both POSIX and Windows, but only when the
    source and destination are on the same volume -- so the temp file is
    created in the destination's own directory, never in a system temp
    directory.

    Sidecars need this as much as the manifest does. A backtest republishes
    its bundle on every run and the API server is threaded, so a plain
    write leaves a window where a reader holding the still-valid previous
    manifest is served a half-written dataset. A partial write also used to
    leave the old manifest pointing at new, incomplete sidecars -- exactly
    the state that writing the manifest last is meant to make impossible.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=str(path.parent))
    try:
        # newline="" disables newline translation. Without it Windows writes
        # CRLF while the recorded sha256 is computed over the LF string, so
        # every digest in every published bundle failed to match its own file
        # -- the integrity check was not merely unverified but wrong.
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    try:
        serialized = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise ContractError(f"dataset payload for {path} contains a non-finite number: {exc}") from exc
    _write_text_atomically(path, serialized, prefix=".dataset-")
    return serialized


def _write_manifest_atomically(bundle_dir: Path, manifest: Dict[str, Any]) -> None:
    try:
        serialized = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise ContractError(f"manifest contains a non-finite number: {exc}") from exc
    _write_text_atomically(bundle_dir / MANIFEST_FILENAME, serialized, prefix=".manifest-")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


def publish_bundle(
    result_dir: Any,
    identity: Mapping[str, Any],
    datasets: Sequence[Dataset],
    capabilities: Mapping[str, Any],
    warnings: Sequence[Mapping[str, Any]],
) -> Path:
    """Validate and publish a visualization bundle under ``result_dir``.

    Every check below runs before anything touches the filesystem, so an
    invalid call leaves ``result_dir`` untouched. Sidecars are written
    next; ``manifest.json`` is written last, atomically, so a reader only
    ever sees the previous complete manifest or the new one -- never a
    partial file. Returns the ``visualization/`` bundle directory.

    ``identity["run_id"]`` is the human-readable run identifier (by
    convention, the result directory's basename) and is required.
    ``identity["bundle_id"]`` is an optional, separate catalog identifier;
    when omitted it defaults to ``run_id`` for backward compatibility, but
    callers whose ``run_id`` values are not unique across the catalog (for
    example, several result directories sharing a basename under
    different parent directories) MUST supply an explicit, unique
    ``bundle_id`` -- the catalog is keyed on it, and a collision silently
    hides one of the colliding runs.
    """

    run_id = identity.get("run_id")
    if not run_id:
        raise ContractError("identity must include a non-empty 'run_id'")

    kinds = [dataset.kind for dataset in datasets]
    if "trades" not in kinds or "performance" not in kinds:
        raise ContractError("a bundle requires both a 'trades' dataset and a 'performance' dataset")

    dataset_ids = [dataset.dataset_id for dataset in datasets]
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ContractError(f"duplicate dataset_id among {dataset_ids!r}")

    normalized_paths = [_validate_relative_path(dataset.path) for dataset in datasets]
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ContractError(f"duplicate dataset path among {normalized_paths!r}")

    bundle_dir = Path(result_dir) / BUNDLE_DIRNAME
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = bundle_dir.resolve()

    descriptors: List[Dict[str, Any]] = []
    for dataset, normalized_path in zip(datasets, normalized_paths):
        target = bundle_dir / normalized_path
        resolved = target.resolve()
        if resolved != bundle_root and bundle_root not in resolved.parents:
            raise ContractError(f"dataset path escapes the bundle directory: {dataset.path!r}")
        serialized = _write_json(target, dataset.payload)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        descriptors.append(
            {
                "dataset_id": dataset.dataset_id,
                "kind": dataset.kind,
                "path": normalized_path,
                "record_count": dataset.record_count,
                "first_timestamp": dataset.first_timestamp,
                "last_timestamp": dataset.last_timestamp,
                "sha256": digest,
            }
        )

    bundle_id = identity.get("bundle_id")
    if not bundle_id:
        bundle_id = run_id

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": str(bundle_id),
        "mode": identity.get("mode"),
        "status": "complete",
        "generated_at": _now_iso(),
        "run": {
            "run_id": run_id,
            "strategy_id": identity.get("strategy_id"),
            "strategy_version": identity.get("strategy_version"),
            "profile_id": identity.get("profile_id"),
        },
        "instrument": {
            "symbol": identity.get("symbol"),
            "asset_class": identity.get("asset_class"),
            "currency": identity.get("currency"),
            "exchange": identity.get("exchange"),
            "contract_multiplier": identity.get("contract_multiplier"),
            "price_precision": identity.get("price_precision"),
        },
        "execution_authority": "none",
        "warnings": list(warnings),
        "capabilities": dict(capabilities),
        "datasets": descriptors,
    }

    _write_manifest_atomically(bundle_dir, manifest)
    return bundle_dir


def read_manifest(bundle_dir: Any) -> Dict[str, Any]:
    """Load ``manifest.json`` from ``bundle_dir``.

    Raises ``ContractError`` when the manifest is absent or unparseable --
    a directory without a valid manifest is not a bundle.
    """

    manifest_path = Path(bundle_dir) / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ContractError(f"no manifest found at {manifest_path}")
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"manifest at {manifest_path} could not be parsed: {exc}") from exc
