"""The catalog is assembled once and reused until a manifest actually changes.

Re-reading every bundle manifest on every request made concurrent requests
serialize on IO and the GIL. Measured against the real 70-bundle catalog, one
``GET /api/runs`` took 0.23s but 48 concurrent took 19.1s, with the slowest
single request at 19.0s -- past the dashboard's timeout. That is the ordinary
load path, not a stress case: the dashboard issues one catalog request plus one
dataset request per discovered run, and every one of those re-read all 70
manifests.

Caching is only sound if staleness is *detected*. A rerun republishes its
bundle in place, so the tests below pin that a republished, added, or removed
bundle is picked up on the very next call -- never served from a stale cache.

The staleness signal is per-manifest (path, mtime, size, file id), all from the
single ``stat`` the walk already performs. Each component is pinned separately
below, because each covers a case the others miss:

- ``mtime`` alone is not enough. Windows timestamps have ~15ms granularity;
  measured here, 8 of 19 back-to-back same-size rewrites were indistinguishable
  by mtime.
- ``size`` alone is not enough: a republished manifest routinely keeps its
  length (a new ``generated_at`` timestamp is the same width as the old one).
- the file id covers the case the other two share a blind spot on, and is the
  strongest signal for how bundles are actually published: ``publish_bundle``
  writes ``manifest.json`` via a temp file plus ``os.replace``, which yields a
  new file id on every republish even within one clock tick.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

from ai_trade import server
from ai_trade.server import build_catalog, reset_catalog_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    """No test may inherit another's catalog, in either direction."""

    reset_catalog_cache()
    yield
    reset_catalog_cache()


def _manifest_text(bundle_id: str, symbol: str) -> str:
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "bundle_id": bundle_id,
            "mode": "historical_backtest",
            "status": "complete",
            "run": {"run_id": bundle_id, "strategy_id": "strategy_04", "strategy_version": "v1"},
            "instrument": {"symbol": symbol},
            "datasets": [],
        }
    )


def _bundle(tmp_path: Path, bundle_id: str, symbol: str = "SPY") -> Path:
    directory = tmp_path / bundle_id / "visualization"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(_manifest_text(bundle_id, symbol), encoding="utf-8")
    return directory


def _count_manifest_reads(monkeypatch) -> dict:
    """Count real manifest reads, the IO the cache exists to avoid."""

    counter = {"count": 0}
    original = server.read_manifest

    def counting_read_manifest(bundle_dir):
        counter["count"] += 1
        return original(bundle_dir)

    monkeypatch.setattr(server, "read_manifest", counting_read_manifest)
    return counter


def _symbols(tmp_path: Path):
    return sorted(entry["instrument"]["symbol"] for entry in build_catalog([tmp_path]))


def _bundle_ids(tmp_path: Path):
    return sorted(entry["bundle_id"] for entry in build_catalog([tmp_path]))


def test_second_build_does_not_reread_manifests(tmp_path, monkeypatch):
    _bundle(tmp_path, "run_a")
    _bundle(tmp_path, "run_b")
    reads = _count_manifest_reads(monkeypatch)

    first = build_catalog([tmp_path])
    assert reads["count"] == 2

    second = build_catalog([tmp_path])
    assert reads["count"] == 2, "an unchanged catalog was re-read from disk"
    assert [entry["bundle_id"] for entry in second] == [entry["bundle_id"] for entry in first]


def test_filtered_builds_reuse_the_same_scan(tmp_path, monkeypatch):
    """Filtering happens over the cached entries, not over a fresh scan."""

    _bundle(tmp_path, "run_a")
    _bundle(tmp_path, "run_b")
    reads = _count_manifest_reads(monkeypatch)

    build_catalog([tmp_path])
    assert reads["count"] == 2
    filtered = build_catalog([tmp_path], filters={"strategy_version": "v1"})
    assert reads["count"] == 2
    assert [entry["bundle_id"] for entry in filtered] == ["run_a", "run_b"]


def test_republished_bundle_is_not_served_stale(tmp_path):
    """A rerun rewrites manifest.json in place; the next call must see it."""

    from ai_trade.visualization_contract import _write_text_atomically

    bundle = _bundle(tmp_path, "run_a", symbol="SPY")
    assert _symbols(tmp_path) == ["SPY"]

    # Exactly how publish_bundle republishes: temp file plus os.replace.
    _write_text_atomically(
        bundle / "manifest.json", _manifest_text("run_a", "QQQ"), prefix=".manifest-"
    )
    assert _symbols(tmp_path) == ["QQQ"]


def test_same_size_rewrite_is_picked_up(tmp_path):
    """Size cannot carry the check: a republish usually keeps its length."""

    bundle = _bundle(tmp_path, "run_a", symbol="SPY")
    manifest = bundle / "manifest.json"
    before = manifest.stat().st_size
    assert _symbols(tmp_path) == ["SPY"]

    manifest.write_text(_manifest_text("run_a", "QQQ"), encoding="utf-8")
    assert manifest.stat().st_size == before, "test no longer exercises a same-size rewrite"
    assert _symbols(tmp_path) == ["QQQ"]


def test_same_mtime_rewrite_is_picked_up(tmp_path):
    """mtime cannot carry the check either: Windows ticks at ~15ms."""

    bundle = _bundle(tmp_path, "run_a", symbol="SPY")
    manifest = bundle / "manifest.json"
    before = manifest.stat()
    assert _symbols(tmp_path) == ["SPY"]

    manifest.write_text(_manifest_text("run_a", "NASDAQ_QQQ"), encoding="utf-8")
    os.utime(manifest, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert manifest.stat().st_mtime_ns == before.st_mtime_ns
    assert _symbols(tmp_path) == ["NASDAQ_QQQ"]


def test_added_bundle_is_picked_up(tmp_path):
    _bundle(tmp_path, "run_a")
    assert _bundle_ids(tmp_path) == ["run_a"]

    _bundle(tmp_path, "run_b")
    assert _bundle_ids(tmp_path) == ["run_a", "run_b"]


def test_removed_bundle_is_dropped(tmp_path):
    _bundle(tmp_path, "run_a")
    bundle_b = _bundle(tmp_path, "run_b")
    assert _bundle_ids(tmp_path) == ["run_a", "run_b"]

    (bundle_b / "manifest.json").unlink()
    assert _bundle_ids(tmp_path) == ["run_a"]


def test_concurrent_builds_share_a_single_scan(tmp_path, monkeypatch):
    """The timeout fix itself: a burst costs one scan, not one per request.

    Reads are pinned exactly, not bounded: once the catalog is scanned its
    staleness signal stops changing, so no later caller re-reads anything
    however many arrive. Before caching this was 48 * 20 = 960 reads.
    """

    for index in range(20):
        _bundle(tmp_path, "run_%02d" % index)
    reads = _count_manifest_reads(monkeypatch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
        counts = list(pool.map(lambda _: len(build_catalog([tmp_path])), range(48)))

    assert counts == [20] * 48
    assert reads["count"] == 20


@contextmanager
def _running_server():
    httpd = server.create_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d" % httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def test_second_catalog_request_does_not_reread_manifests(tmp_path, monkeypatch):
    """The same guarantee over HTTP, which is where the timeout was measured."""

    _bundle(tmp_path, "run_a")
    _bundle(tmp_path, "run_b")
    monkeypatch.setattr(server, "CATALOG_ROOTS", [tmp_path])
    reads = _count_manifest_reads(monkeypatch)

    with _running_server() as base_url:
        first = _get_json(base_url + "/api/runs")
        assert reads["count"] == 2
        second = _get_json(base_url + "/api/runs")
        assert reads["count"] == 2, "a second request re-read every manifest"

    assert [entry["bundle_id"] for entry in first] == ["run_a", "run_b"]
    assert second == first


def test_health_route_reports_from_the_cache(tmp_path, monkeypatch):
    _bundle(tmp_path, "run_a")
    (tmp_path / "broken" / "visualization").mkdir(parents=True)
    (tmp_path / "broken" / "visualization" / "manifest.json").write_text("{oops", encoding="utf-8")
    monkeypatch.setattr(server, "CATALOG_ROOTS", [tmp_path])
    reads = _count_manifest_reads(monkeypatch)

    with _running_server() as base_url:
        first = _get_json(base_url + "/health")
        assert reads["count"] == 2
        assert _get_json(base_url + "/health") == first
        assert reads["count"] == 2

    assert first["valid_bundles"] == 1
    assert first["invalid_bundles"] == 1
