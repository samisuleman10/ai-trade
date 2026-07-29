import json
from pathlib import Path

import pytest

from ai_trade.server import _validate_relative_dataset_path, build_catalog, resolve_dataset_path


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


# The manifest is attacker-reachable input as far as this function is
# concerned: it decides which file the HTTP dataset route opens. Rejecting
# traversal on Windows is a stated constraint, but only the POSIX form was
# exercised, and Windows has several escape shapes a "/"-only check misses.
TRAVERSAL_PATHS = [
    "C:\\x",                 # absolute, drive-qualified
    "C:x",                   # drive-relative: resolves against C:'s current dir
    "\\\\server\\share\\x",  # UNC path to another host
    "data\\..\\..\\x",       # backslash-separated traversal
    "..\\..\\..\\Windows\\System32\\config\\SAM",
    "\\Windows\\x",          # root-relative on the current drive
]


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
def test_windows_path_traversal_is_rejected(tmp_path, bad_path):
    bundle = _bundle(tmp_path, "run_a", "strategy_04", "SPY")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["datasets"].append({"dataset_id": "evil", "kind": "trades", "path": bad_path})
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_dataset_path(bundle, "evil")


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
def test_string_validation_alone_rejects_windows_traversal_forms(bad_path):
    """Assert the string layer directly, not just resolve_dataset_path's outcome.

    resolve_dataset_path also resolves the joined path and compares it
    against the bundle root, so most forms are refused twice and a rotted
    string check would stay invisible behind that second guard. The second
    guard does not cover every form: ``C:x`` is drive-relative, and pathlib
    joins it onto a same-drive parent by concatenation, so it lands INSIDE
    the bundle and the resolve-and-compare check never fires. The
    drive-letter rejection here is the only thing stopping it.
    """

    with pytest.raises(ValueError):
        _validate_relative_dataset_path(bad_path)
