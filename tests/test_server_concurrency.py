"""The catalog must survive the dashboard's concurrent dataset fan-out.

The dashboard requests one performance dataset per discovered run. Measured
against the real 48-bundle catalog, a single-threaded server failed 25 of 48
concurrent requests while a threaded one served all 48. The failures surface
as blank numbers in the interface with no error anywhere, so this is a silent
data-loss bug rather than a visible one.

Note on coverage: a cheap endpoint at low concurrency does NOT reproduce the
failure -- connection reuse hides it, and a single-threaded server passes.
The construction assertion below is therefore the real guard; the concurrency
test is a smoke test that the server works under parallel load at all.
"""

from __future__ import annotations

import concurrent.futures
import json
import socketserver
import threading
import urllib.request

import pytest

from ai_trade.server import create_server


CONCURRENT_REQUESTS = 48


def test_server_is_constructed_with_threading():
    """A regression to a plain HTTPServer silently blanks the dashboard."""

    server = create_server(0)
    try:
        assert isinstance(server, socketserver.ThreadingMixIn)
    finally:
        server.server_close()


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


def test_parallel_catalog_requests_all_succeed(running_server):
    url = running_server + "/api/runs"

    def fetch(_: int) -> int:
        with urllib.request.urlopen(url, timeout=15) as response:
            json.loads(response.read().decode("utf-8"))
            return response.status

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as pool:
        statuses = list(pool.map(fetch, range(CONCURRENT_REQUESTS)))

    assert statuses == [200] * CONCURRENT_REQUESTS
