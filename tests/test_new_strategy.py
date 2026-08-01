"""The scaffolder writes the places logic goes — and stubs that fail loudly.

The property these tests protect: a generated strategy must raise
``NotImplementedError`` rather than return ``[]``. A skeleton that silently
produced zero signals would be indistinguishable from a valid negative result
("this strategy found no trades"), the worst failure mode this repo can
produce. Everything is generated into ``tmp_path`` so the working tree is
never touched.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

from ai_trade.new_strategy import main

ARGS = [
    "--id", "strategy_99",
    "--title", "Strategy 99",
    "--subtitle", "Scaffolder test strategy",
]


def _scaffold(root: Path, *extra: str) -> int:
    return main(ARGS + ["--root", str(root)] + list(extra))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_rules_stub_raises_instead_of_returning_no_signals(tmp_path):
    assert _scaffold(tmp_path) == 0
    module = _load_module(
        tmp_path / "src" / "ai_trade" / "strategy_99_v1.py",
        "generated_strategy_99_v1",
    )
    params = module.Strategy99V1ExecutionParameters()
    # Empty inputs are exactly the case where the shared loop would return []
    # without ever calling the hooks — the guard raise must fire regardless.
    with pytest.raises(NotImplementedError) as excinfo:
        module.signals_from_zone_events_strategy_99_v1([], [], [], params)
    message = str(excinfo.value)
    assert "strategy_99_v1.py" in message
    assert "_reaction_filter" in message and "_extra_columns" in message


def test_generated_candidate_signals_also_raises(tmp_path):
    assert _scaffold(tmp_path) == 0
    module = _load_module(
        tmp_path / "src" / "ai_trade" / "strategy_99_v1.py",
        "generated_strategy_99_v1_candidates",
    )
    with pytest.raises(NotImplementedError):
        module.candidate_signals_strategy_99_v1([], [])


def test_generated_hook_stubs_raise_individually(tmp_path):
    # Even after someone deletes the guard raise, unimplemented hooks must
    # still fail loudly on the first matching reaction.
    assert _scaffold(tmp_path) == 0
    module = _load_module(
        tmp_path / "src" / "ai_trade" / "strategy_99_v1.py",
        "generated_strategy_99_v1_hooks",
    )
    with pytest.raises(NotImplementedError):
        module._reaction_filter(None, None)
    with pytest.raises(NotImplementedError):
        module._extra_columns(None, None)


def test_generated_audit_skeleton_raises_and_is_stdlib_only(tmp_path):
    assert _scaffold(tmp_path) == 0
    audit_path = tmp_path / "src" / "ai_trade" / "audit_rules_strategy_99_v1.py"
    module = _load_module(audit_path, "generated_audit_rules_strategy_99_v1")
    with pytest.raises(NotImplementedError) as excinfo:
        module.audit_row({}, frozenset(), {})
    assert "audit_rules_strategy_99_v1.py" in str(excinfo.value)

    # The independence rule from the safety property: the audit must never
    # import strategy code — the skeleton must not even hint at doing so.
    tree = ast.parse(audit_path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "generated audit must not use relative imports"
            imported.append(node.module or "")
    assert all(not name.startswith("ai_trade") for name in imported), imported


def test_spec_skeleton_has_the_sections_the_research_skill_requires(tmp_path):
    assert _scaffold(tmp_path) == 0
    spec = (
        tmp_path / "strategies" / "strategy_99" / "v1" / "strategy.md"
    ).read_text(encoding="utf-8")
    for heading in (
        "## Purpose",
        "## Motivating observation",
        "## Rules",
        "## Required ablation",
        "## Producer output required for auditing",
        "## Research warning",
        "## Promotion criteria",
    ):
        assert heading in spec, heading


def test_registry_entry_is_printed_not_written(tmp_path, capsys):
    assert _scaffold(tmp_path) == 0
    out = capsys.readouterr().out
    assert 'StrategySpec(' in out
    assert 'VersionSpec(' in out
    assert 'version_id="strategy_99_v1"' in out
    # The generator must not create or edit a registry file anywhere.
    assert not (tmp_path / "src" / "ai_trade" / "strategy_registry.py").exists()


def test_refuses_to_overwrite_without_force(tmp_path):
    assert _scaffold(tmp_path) == 0
    spec_doc = tmp_path / "strategies" / "strategy_99" / "v1" / "strategy.md"
    sentinel = "HAND-EDITED CONTENT THAT MUST SURVIVE"
    spec_doc.write_text(sentinel, encoding="utf-8")

    assert _scaffold(tmp_path) == 1
    assert spec_doc.read_text(encoding="utf-8") == sentinel

    assert _scaffold(tmp_path, "--force") == 0
    assert sentinel not in spec_doc.read_text(encoding="utf-8")


def test_refusal_writes_nothing_at_all(tmp_path):
    # All-or-nothing: if even one target exists, no other target is written.
    spec_doc = tmp_path / "strategies" / "strategy_99" / "v1" / "strategy.md"
    spec_doc.parent.mkdir(parents=True)
    spec_doc.write_text("pre-existing", encoding="utf-8")

    assert _scaffold(tmp_path) == 1
    assert not (tmp_path / "src" / "ai_trade" / "strategy_99_v1.py").exists()
    assert not (
        tmp_path / "src" / "ai_trade" / "audit_rules_strategy_99_v1.py"
    ).exists()


def test_malformed_id_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main(
            ["--id", "strategy-99", "--title", "x", "--subtitle", "y",
             "--root", str(tmp_path)]
        )
    assert not (tmp_path / "strategies").exists()
