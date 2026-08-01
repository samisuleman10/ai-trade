"""Cross-variant ablation table for Strategy 04 v1.2.

Thin wrapper: the table builder lives in ``summarize_version_ablation`` and
reads the registry entry, so the symbol list, the variant list and the
threshold-consistency guard cannot drift from the runs themselves -- a
hardcoded copy here is how IWM, GLD and SLV were once silently omitted.
This module keeps the historical CLI and the exports other modules and
tests import. Interpretation stays with the human: the spec's promotion
criteria require out-of-sample confirmation and sensitivity evidence the
table alone cannot provide.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_trade.strategy_registry import VERSIONS
from ai_trade.summarize_version_ablation import build_grid as _build_grid
from ai_trade.summarize_version_ablation import render_markdown as _render_markdown
from ai_trade.summarize_version_ablation import write_summary

_SPEC = VERSIONS["strategy_04_v1_2"]

SYMBOLS = _SPEC.supported_symbols
VARIANTS = tuple(_SPEC.variants)


def build_grid(results_root: Path) -> dict[str, dict[str, object]]:
    """Load every symbol's reports into {symbol: {max_risk_zone_ratio, variants}}."""
    return _build_grid(_SPEC, results_root)


def render_markdown(grid: dict[str, dict[str, object]]) -> str:
    return _render_markdown(_SPEC, grid)


def main() -> int:
    # The parser stays here so this CLI's surface (flags, defaults, error
    # text) is exactly what it was before the generic module existed.
    parser = argparse.ArgumentParser(description="Summarize the v1.2 ablation grid.")
    parser.add_argument("--results-root", type=Path,
                        default=Path("strategies/strategy_04/v1_2/results"))
    args = parser.parse_args()
    return write_summary(_SPEC, args.results_root)


if __name__ == "__main__":
    raise SystemExit(main())
