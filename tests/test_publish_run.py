import json
from pathlib import Path

from ai_trade.publish_run import publish_result_directory

from tests.test_backfill_visualization_bundles import _make_result


def test_publishing_a_finished_result_directory_creates_a_bundle(tmp_path):
    _make_result(tmp_path / "run")
    bundle = publish_result_directory(tmp_path / "run")
    assert bundle is not None
    assert (bundle / "manifest.json").exists()


def test_publishing_returns_none_when_requirements_are_missing(tmp_path):
    (tmp_path / "bare").mkdir()
    assert publish_result_directory(tmp_path / "bare") is None
