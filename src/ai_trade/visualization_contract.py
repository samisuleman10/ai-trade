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
