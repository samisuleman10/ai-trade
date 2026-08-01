"""Export the registry's strategy identity layer for the dashboard.

The frontend used to hand-declare that each strategy exists, which meant a
strategy registered in Python was invisible in the dashboard until someone
re-typed its name into TypeScript. This module writes the *identity* fields
(id, title, subtitle, spec document, version ids) to a JSON the frontend
imports, so existence and naming have one source of truth: ``STRATEGIES``.

Only identity is exported. The rich per-version display config (version
chips, variant descriptions, spec prose) is editorial content that lives in
TypeScript on purpose -- see ``dashboard/src/deepdive/strategy04Config.ts``.

The output is committed, not built on the fly, so the dashboard needs no
Python at build time; ``tests/test_export_strategy_registry.py`` fails when
the committed file drifts from the registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ai_trade.strategy_registry import STRATEGIES

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "dashboard" / "src" / "generated" / "strategies.json"

# Recorded inside the JSON itself: the file carries its own regeneration
# instructions because anyone reading it in the dashboard tree is two
# directories away from discovering this module by accident.
REGENERATE_COMMAND = "python -m ai_trade.export_strategy_registry"


def registry_payload() -> Dict[str, Any]:
    """The exact object serialised to disk, exposed so the test can compare.

    Key order is authored, not sorted: strategies appear in registry order
    (oldest first, matching ``STRATEGIES`` insertion order) so the export is
    byte-for-byte deterministic and diffs read chronologically.
    """
    return {
        "comment": (
            "Generated file -- do not edit by hand. "
            f"Regenerate with: {REGENERATE_COMMAND}"
        ),
        "strategies": [
            {
                "strategy_id": strategy.strategy_id,
                "title": strategy.title,
                "subtitle": strategy.subtitle,
                "spec_document": strategy.spec_document,
                "version_ids": [spec.version_id for spec in strategy.versions],
            }
            for strategy in STRATEGIES.values()
        ],
    }


def rendered_json() -> str:
    """Serialise the payload the one canonical way (also used by the test)."""
    return json.dumps(registry_payload(), indent=2) + "\n"


def export(path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the committed bytes identical across platforms;
    # without it Windows would write CRLF and every regeneration would diff.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered_json())
    return path


def main() -> None:
    written = export()
    print(f"Wrote {written.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
