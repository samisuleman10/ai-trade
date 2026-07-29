"""Sidecars publish atomically, and the API does not hand its data to any origin.

Both behaviours were review findings. A plain sidecar write left a window where
a reader holding the still-valid previous manifest could be served a
half-written dataset, and a wildcard CORS header let any page open in the
browser read the whole run catalogue.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ai_trade.server import ALLOWED_ORIGINS, create_server
from ai_trade.visualization_contract import (
    _write_json,
    build_performance,
    build_trade_ledger,
    publish_bundle,
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
        }
    ]


def _summary():
    return {
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


def _identity():
    return {
        "bundle_id": "demo_bundle",
        "run_id": "demo_run",
        "strategy_id": "strategy_04",
        "strategy_version": "v1_1",
        "symbol": "SPY",
        "mode": "historical_backtest",
    }


def test_sidecar_write_leaves_no_partial_file_behind(tmp_path):
    """A failed sidecar write must not replace the previous good one."""

    target = tmp_path / "data" / "trades-fixed.json"
    _write_json(target, {"trades": ["original"]})
    original = target.read_text(encoding="utf-8")

    # A non-finite number is rejected during serialisation, before any write.
    with pytest.raises(Exception):
        _write_json(target, {"trades": [float("nan")]})

    assert target.read_text(encoding="utf-8") == original
    leftovers = [p.name for p in target.parent.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_publish_leaves_no_temp_files_in_the_bundle(tmp_path):
    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    bundle = publish_bundle(tmp_path, _identity(), datasets, {}, [])
    stray = [str(p) for p in Path(bundle).rglob("*.tmp")]
    assert stray == []


def test_recorded_digest_matches_the_sidecar_on_disk(tmp_path):
    """Proves the file that landed is the one the manifest describes."""

    import hashlib

    datasets = [
        build_trade_ledger(_rows(), "fixed", "demo_run"),
        build_performance(_rows(), _summary(), "fixed", 100000.0),
    ]
    bundle = publish_bundle(tmp_path, _identity(), datasets, {}, [])
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    for descriptor in manifest["datasets"]:
        raw = (bundle / descriptor["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == descriptor["sha256"]


@pytest.fixture()
def running_server():
    httpd = create_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d" % httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _cors_header_for(url: str, origin: str) -> str:
    request = urllib.request.Request(url, headers={"Origin": origin})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.headers.get("Access-Control-Allow-Origin") or ""


def test_dev_server_origin_is_allowed(running_server):
    assert _cors_header_for(running_server + "/health", ALLOWED_ORIGINS[0]) == ALLOWED_ORIGINS[0]


def test_foreign_origin_gets_no_cors_grant(running_server):
    """A wildcard here would let any open page read every trade ledger."""

    assert _cors_header_for(running_server + "/health", "https://evil.example") == ""
