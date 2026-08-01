"""The committed dashboard JSON must match the Python registry exactly.

The dashboard imports ``dashboard/src/generated/strategies.json`` at build
time instead of calling Python, so the file is committed. That trade-off only
holds if drift is loud: this test compares the committed bytes against a
fresh render, so registering (or renaming) a strategy without re-running the
exporter fails CI instead of shipping a stale tab bar.
"""

from __future__ import annotations

import json

from ai_trade.export_strategy_registry import (
    OUTPUT_PATH,
    REGENERATE_COMMAND,
    registry_payload,
    rendered_json,
)
from ai_trade.strategy_registry import STRATEGIES

STALE_HINT = f"dashboard/src/generated/strategies.json is stale; run: {REGENERATE_COMMAND}"


def test_committed_json_is_byte_identical_to_a_fresh_render():
    # Byte comparison, not just parsed equality: formatting drift (hand edits,
    # CRLF, re-ordered keys) would make every future regeneration a noisy diff.
    assert OUTPUT_PATH.read_text(encoding="utf-8") == rendered_json(), STALE_HINT


def test_payload_mirrors_strategies_one_to_one():
    strategies = registry_payload()["strategies"]
    assert [entry["strategy_id"] for entry in strategies] == list(STRATEGIES)
    for entry in strategies:
        spec = STRATEGIES[entry["strategy_id"]]
        assert entry["title"] == spec.title
        assert entry["subtitle"] == spec.subtitle
        assert entry["spec_document"] == spec.spec_document
        assert entry["version_ids"] == [v.version_id for v in spec.versions]


def test_export_names_its_regeneration_command():
    # The JSON travels far from this module; it must carry its own provenance.
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert REGENERATE_COMMAND in payload["comment"]
