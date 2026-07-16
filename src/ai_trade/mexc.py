"""Read-only MEXC spot and futures account snapshots."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://api.mexc.com"


class MEXCSyncError(RuntimeError):
    """Raised when MEXC rejects or cannot complete a read-only request."""


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without printing or exposing secrets."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _credentials() -> tuple[str, str]:
    load_dotenv()
    key, secret = os.getenv("MEXC_API_KEY", ""), os.getenv("MEXC_API_SECRET", "")
    if not key or not secret:
        raise MEXCSyncError("Set MEXC_API_KEY and MEXC_API_SECRET in .env before syncing.")
    return key, secret


def _get(path: str, headers: Mapping[str, str], params: Mapping[str, Any] | None = None) -> Any:
    query = urlencode(params or {})
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS base URL
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise MEXCSyncError(f"MEXC request failed ({error.code}): {detail}") from error
    except URLError as error:
        raise MEXCSyncError(f"Could not reach MEXC: {error.reason}") from error


def _spot_account(key: str, secret: str) -> dict[str, Any]:
    params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
    query = urlencode(params)
    signature = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return _get("/api/v3/account", {"X-MEXC-APIKEY": key}, {**params, "signature": signature})


def _futures_get(path: str, key: str, secret: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    timestamp = str(int(time.time() * 1000))
    query = urlencode(sorted((params or {}).items()))
    signature = hmac.new(secret.encode(), f"{key}{timestamp}{query}".encode(), hashlib.sha256).hexdigest()
    data = _get(path, {"ApiKey": key, "Request-Time": timestamp, "Signature": signature}, params)
    if not data.get("success", False):
        raise MEXCSyncError(f"MEXC futures request failed: {data.get('code')} {data.get('message', '')}".strip())
    return data


def fetch_futures_history(limit: int = 100) -> dict[str, Any]:
    """Return the most recent closed futures positions; this request is read-only."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    key, secret = _credentials()
    return _futures_get(
        "/api/v1/private/position/list/history_positions",
        key,
        secret,
        {"page_num": 1, "page_size": limit},
    )


def fetch_account() -> dict[str, Any]:
    """Read spot balances plus futures equity and open positions; never trade or transfer."""
    key, secret = _credentials()
    spot = _spot_account(key, secret)
    futures_assets = _futures_get("/api/v1/private/account/assets", key, secret)
    futures_positions = _futures_get("/api/v1/private/position/open_positions", key, secret)
    return {
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "spot": {
            "balances": [
                balance for balance in spot.get("balances", [])
                if balance.get("free") not in {"0", "0.0", "0.00000000"} or balance.get("locked") not in {"0", "0.0", "0.00000000"}
            ],
            "permissions": spot.get("permissions", []),
        },
        "futures": {"assets": futures_assets.get("data", []), "positions": futures_positions.get("data", [])},
    }


def save_snapshot(snapshot: dict[str, Any], directory: Path = Path("data/mexc")) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"mexc-{stamp}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
