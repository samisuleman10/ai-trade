"""Read-only catalog API over published visualization bundles.

Serves the run catalog, manifests, and declared datasets for any directory
that published a valid ``visualization/manifest.json``. It never computes
indicators, derives summaries, or invents data: a value reaches a client
only if a producer wrote it to a validated bundle first.
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import urllib.parse

from ai_trade.visualization_contract import ContractError, read_manifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Roots scanned for visualization bundles. A bundle is any directory named
# ``visualization`` (at any depth under these roots) that contains a
# parseable ``manifest.json`` -- see ``read_manifest``. Matches the roots
# used by the Task 2 backfill script (``backfill_visualization_bundles``).
CATALOG_ROOTS: List[Path] = [PROJECT_ROOT / "outputs", PROJECT_ROOT / "strategies"]

# Manifest fields eligible for exact-match filtering via query params.
_INSTRUMENT_FILTER_KEYS = ("symbol",)
_RUN_FILTER_KEYS = ("strategy_id", "strategy_version")
_TOP_LEVEL_FILTER_KEYS = ("mode",)

_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:")
_MANIFEST_ROUTE_RE = re.compile(r"^/api/runs/(?P<bundle_id>[^/]+)/manifest$")
_DATASET_ROUTE_RE = re.compile(r"^/api/runs/(?P<bundle_id>[^/]+)/datasets/(?P<dataset_id>[^/]+)$")


def _iter_manifest_paths(roots: Iterable[Any]) -> Iterable[Path]:
    """Yield every ``visualization/manifest.json`` found under ``roots``.

    Directories that merely happen to be named ``visualization`` but hold
    no ``manifest.json`` (e.g. a bundle mid-write, or an unrelated folder)
    never appear here -- they are not bundles, partially or otherwise.
    """

    seen = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for manifest_path in sorted(root.rglob("visualization/manifest.json")):
            resolved = manifest_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield manifest_path


def _entry_from_manifest(manifest: Any, bundle_dir: Path) -> Optional[Dict[str, Any]]:
    """Build a catalog entry from a parsed manifest, or None if malformed.

    A manifest that parses as JSON but lacks the shape a catalog entry
    needs (not an object, no usable ``bundle_id``) is treated the same as
    an unparseable one: omitted, not partially served.
    """

    if not isinstance(manifest, dict):
        return None
    bundle_id = manifest.get("bundle_id")
    if not isinstance(bundle_id, str) or not bundle_id:
        return None

    run = manifest.get("run")
    if not isinstance(run, dict):
        run = {}
    instrument = manifest.get("instrument")
    if not isinstance(instrument, dict):
        instrument = {}
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        datasets = []
    dataset_ids = [
        dataset.get("dataset_id")
        for dataset in datasets
        if isinstance(dataset, dict) and isinstance(dataset.get("dataset_id"), str)
    ]
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}

    return {
        "bundle_id": bundle_id,
        "run": run,
        "instrument": instrument,
        "mode": manifest.get("mode"),
        "generated_at": manifest.get("generated_at"),
        "capabilities": capabilities,
        "dataset_ids": dataset_ids,
        "bundle_dir": bundle_dir,
    }


def _scan_bundles(roots: Iterable[Any]) -> Tuple[List[Dict[str, Any]], int]:
    """Parse every discovered manifest, returning (valid entries, invalid count).

    "Invalid" covers anything ``read_manifest`` rejects (missing/unparseable
    JSON) as well as manifests that parse but are structurally unusable
    (see ``_entry_from_manifest``). Either way the directory is excluded
    from the catalog rather than served partially.
    """

    entries: List[Dict[str, Any]] = []
    invalid_count = 0
    for manifest_path in _iter_manifest_paths(roots):
        bundle_dir = manifest_path.parent
        try:
            manifest = read_manifest(bundle_dir)
        except ContractError:
            invalid_count += 1
            continue
        entry = _entry_from_manifest(manifest, bundle_dir)
        if entry is None:
            invalid_count += 1
            continue
        entries.append(entry)
    return entries, invalid_count


def _entry_matches(entry: Dict[str, Any], filters: Dict[str, str]) -> bool:
    for key, value in filters.items():
        if key in _TOP_LEVEL_FILTER_KEYS:
            if entry.get(key) != value:
                return False
        elif key in _RUN_FILTER_KEYS:
            if entry.get("run", {}).get(key) != value:
                return False
        elif key in _INSTRUMENT_FILTER_KEYS:
            if entry.get("instrument", {}).get(key) != value:
                return False
        else:
            # Unknown filter key: never matches. Callers should only pass
            # the documented filter keys.
            return False
    return True


def build_catalog(
    roots: Iterable[Any], filters: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Discover every valid visualization bundle under ``roots``.

    Walks each root for ``visualization/manifest.json``, parses each with
    ``read_manifest``, and silently skips anything unparseable or
    structurally unusable -- see ``_scan_bundles``. Each surviving entry
    carries ``bundle_id``, ``run``, ``instrument``, ``mode``,
    ``generated_at``, ``capabilities``, ``dataset_ids``, and the bundle
    directory (``bundle_dir``, for internal routing use -- not meant to be
    serialized verbatim to clients).

    ``filters`` compares by exact equality only (never substring/prefix)
    against ``mode``, ``run.strategy_id``, ``run.strategy_version``, and
    ``instrument.symbol``.
    """

    filters = filters or {}
    entries, _ = _scan_bundles(roots)
    return [entry for entry in entries if _entry_matches(entry, filters)]


def _validate_relative_dataset_path(raw_path: Any) -> str:
    """Reject anything but a clean relative path, raising ValueError.

    Mirrors the checks in ``visualization_contract._validate_relative_path``
    but raises ``ValueError`` (this module's contract for a rejected
    dataset path) instead of ``ContractError``. Handles Windows-specific
    forms explicitly: drive letters (``C:\\...`` / ``C:foo``), backslash
    separators, and UNC paths (``\\\\server\\share\\...``, which normalize
    to a leading ``//`` and are caught by the absolute-path check).
    """

    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"dataset path must be a non-empty string, got {raw_path!r}")
    if _DRIVE_LETTER_RE.match(raw_path):
        raise ValueError(f"dataset path must not contain a drive letter: {raw_path!r}")
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError(f"dataset path must not be absolute: {raw_path!r}")
    segments = normalized.split("/")
    if ".." in segments:
        raise ValueError(f"dataset path must not escape the bundle directory: {raw_path!r}")
    if any(segment == "" for segment in segments):
        raise ValueError(f"dataset path must not contain empty segments: {raw_path!r}")
    return normalized


def resolve_dataset_path(bundle_dir: Any, dataset_id: str) -> Path:
    """Resolve ``dataset_id`` to a real file path declared by the manifest.

    Raises ``KeyError`` when ``dataset_id`` is not declared by the bundle's
    manifest. Raises ``ValueError`` when the declared path is absolute,
    has a drive letter, contains ``..``, or -- as a final defence-in-depth
    check independent of the string-level rejections above -- resolves
    outside ``bundle_dir`` once actually joined and resolved on disk (this
    catches anything the string checks alone might miss, e.g. symlinks).
    """

    bundle_dir = Path(bundle_dir)
    manifest = read_manifest(bundle_dir)
    datasets = manifest.get("datasets") if isinstance(manifest, dict) else None
    if not isinstance(datasets, list):
        datasets = []

    declared = None
    for dataset in datasets:
        if isinstance(dataset, dict) and dataset.get("dataset_id") == dataset_id:
            declared = dataset
            break
    if declared is None:
        raise KeyError(f"dataset {dataset_id!r} is not declared by the manifest")

    normalized = _validate_relative_dataset_path(declared.get("path"))

    bundle_root = bundle_dir.resolve()
    target = (bundle_dir / normalized).resolve()
    if target != bundle_root and bundle_root not in target.parents:
        raise ValueError(f"dataset path escapes the bundle directory: {declared.get('path')!r}")
    return target


def _find_bundle_entry(bundle_id: str) -> Optional[Dict[str, Any]]:
    for entry in build_catalog(CATALOG_ROOTS):
        if entry["bundle_id"] == bundle_id:
            return entry
    return None


def _serializable_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Drop internal-only fields (``bundle_dir``) before sending to a client."""

    return {key: value for key, value in entry.items() if key != "bundle_dir"}


# Only pages served from this machine may read the API. A wildcard let any
# site open in the browser read the whole run catalogue and every trade
# ledger while the server was running.
#
# The port is deliberately not pinned: Vite picks the next free port when
# 5173 is taken, and an allowlist of literal origins silently broke the
# dashboard whenever that happened. Restricting the host is what carries the
# security property; the port does not.
LOCAL_ORIGIN_RE = re.compile(r"^http://(?:localhost|127\.0\.0\.1)(?::\d{1,5})?$")


def is_local_origin(origin: Optional[str]) -> bool:
    return bool(origin) and LOCAL_ORIGIN_RE.match(origin or "") is not None


class StrategyApiHandler(BaseHTTPRequestHandler):

    def _allowed_origin(self) -> Optional[str]:
        """Echo the request's origin only when it is served from this machine."""

        origin = self.headers.get("Origin")
        return origin if is_local_origin(origin) else None

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        allowed = self._allowed_origin()
        if allowed is not None:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def _write_json(self, status_code: int, payload: Any) -> None:
        self._set_headers(status_code)
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _write_json_error(self, status_code: int, code: str, message: str) -> None:
        self._write_json(status_code, {"error": message, "code": code})

    def _handle_catalog_route(self, path: str, params: Dict[str, List[str]]) -> bool:
        """Route the read-only catalog endpoints. Returns True if handled.

        This is the whole public surface. Endpoints that returned invented
        strategy specifications and a fictional live shadow position were
        removed: this server only serves data a producer actually published,
        so anything it cannot read from a validated bundle is a 404 rather
        than a plausible-looking placeholder.
        """

        if path == "/health":
            entries, invalid_count = _scan_bundles(CATALOG_ROOTS)
            self._write_json(
                200,
                {
                    "status": "ok",
                    "valid_bundles": len(entries),
                    "invalid_bundles": invalid_count,
                },
            )
            return True

        if path == "/api/runs":
            filters: Dict[str, str] = {}
            for key in ("mode", "strategy_id", "strategy_version", "symbol"):
                values = params.get(key)
                if values:
                    filters[key] = values[0]
            entries = build_catalog(CATALOG_ROOTS, filters=filters)
            self._write_json(200, [_serializable_entry(entry) for entry in entries])
            return True

        manifest_match = _MANIFEST_ROUTE_RE.match(path)
        if manifest_match:
            bundle_id = urllib.parse.unquote(manifest_match.group("bundle_id"))
            entry = _find_bundle_entry(bundle_id)
            if entry is None:
                self._write_json_error(404, "bundle_not_found", f"no bundle with id {bundle_id!r}")
                return True
            try:
                manifest = read_manifest(entry["bundle_dir"])
            except ContractError as exc:
                self._write_json_error(500, "manifest_unreadable", str(exc))
                return True
            self._write_json(200, manifest)
            return True

        dataset_match = _DATASET_ROUTE_RE.match(path)
        if dataset_match:
            bundle_id = urllib.parse.unquote(dataset_match.group("bundle_id"))
            dataset_id = urllib.parse.unquote(dataset_match.group("dataset_id"))
            entry = _find_bundle_entry(bundle_id)
            if entry is None:
                self._write_json_error(404, "bundle_not_found", f"no bundle with id {bundle_id!r}")
                return True
            try:
                dataset_path = resolve_dataset_path(entry["bundle_dir"], dataset_id)
            except KeyError:
                self._write_json_error(404, "dataset_not_found", f"no dataset with id {dataset_id!r}")
                return True
            except ValueError as exc:
                self._write_json_error(400, "invalid_dataset_path", str(exc))
                return True
            try:
                with dataset_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                self._write_json_error(500, "dataset_unreadable", str(exc))
                return True
            self._write_json(200, payload)
            return True

        return False

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        if self._handle_catalog_route(path, params):
            return

        self._write_json_error(404, "endpoint_not_found", f"no endpoint at {path!r}")


def create_server(port: int) -> ThreadingHTTPServer:
    """Build the API server.

    Threading matters: the dashboard requests one dataset per discovered run,
    so a single-threaded server drops most of a 48-run fan-out and the UI
    silently renders blanks where numbers belong.
    """

    return ThreadingHTTPServer(("localhost", port), StrategyApiHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy Visualization REST API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default: 8080)")
    args = parser.parse_args()

    server = create_server(args.port)
    print(f"Server running at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")


if __name__ == "__main__":
    main()
