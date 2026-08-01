"""Scaffold the files a new strategy needs — the places logic goes, and no logic.

``python -m ai_trade.new_strategy --id strategy_05 --title "..." --subtitle "..."``
writes three skeletons (spec document, rules module, audit-rules module) and
prints the registry entry to paste into ``strategy_registry.py`` by hand.

Two deliberate properties:

1. **Every stub raises ``NotImplementedError``.** A generated strategy that
   silently returned zero signals would look exactly like a valid negative
   result — a strategy that "found no trades" — and that is the worst failure
   mode this repo can produce. The rules skeleton therefore raises at the top
   of its signal builder, not merely inside the hooks: the shared causal loop
   never calls the hooks on inputs with no matching reaction, so hook-only
   raises could still let ``[]`` escape.

2. **The registry entry is printed, never written.** A generator that edits
   ``strategy_registry.py`` is how a bad entry lands unreviewed; pasting the
   entry forces a human to read it in a diff.

Existing files are never overwritten unless ``--force`` is given, and the
check runs before anything is written so a refusal leaves no partial output.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from string import Template
from typing import Optional

# src/ai_trade/new_strategy.py -> parents[2] is the repository root. --root
# overrides this for tests, which scaffold into a temp directory instead of
# the working tree.
_REPO_ROOT = Path(__file__).resolve().parents[2]

_ID_PATTERN = re.compile(r"^strategy_\d+$")

# The first version a new strategy gets. Later versions are authored against
# the then-current spec by hand; the scaffolder only covers the cold start.
_VERSION = "v1"


def _camel(strategy_id: str) -> str:
    """``strategy_05`` -> ``Strategy05``, for class names."""
    return "".join(part.capitalize() for part in strategy_id.split("_"))


# ---------------------------------------------------------------------------
# Templates. string.Template ($-substitution) rather than str.format, because
# the generated Python and the printed registry entry are full of literal
# braces ({variant}, dict displays) that .format would mangle.
# ---------------------------------------------------------------------------

# Sections follow .claude/skills/strategy-research/SKILL.md: hypothesis with
# motivating evidence, exact rules, required ablation, auditable columns,
# research warning naming every in-sample parameter, promotion criteria.
_SPEC_TEMPLATE = Template('''\
# $title — Version 1

> GENERATED SKELETON — replace every TODO before writing any code. The spec
> comes first: the rules module and the audit rules are both written from this
> document, independently of each other.

## Purpose

TODO: the hypothesis. What edge is being tested, in one paragraph, and why it
might exist.

## Motivating observation

TODO: the evidence that motivated the hypothesis — reviewed trades, a measured
asymmetry, a published result. A strategy with no motivating observation is a
parameter search, not research.

## Rules

TODO: the exact, causal rules. Every quantity must be computable at decision
time from data already closed; name the timeframe and bar for each input.

## Required ablation

TODO: every switchable rule gets its own variant so any effect is
attributable. The base variant (all new rules off) must reproduce the
incumbent exactly — if it does not, the harness is wrong and no other result
may be read.

| Variant | Rule ... |
| --- | --- |
| $strategy_id-$version-base | off |

## Producer output required for auditing

TODO: list every column ``candidate_signals.csv`` must gain so the audit tool
can verify each rule from recorded evidence rather than recomputation. A rule
whose decision value is not recorded is unauditable.

## Research warning

TODO: name every parameter chosen in-sample and every hypothesis without
supporting measurement. Thresholds are swept, never chosen by code; nothing
here approves paper or live execution.

## Promotion criteria

TODO: the conditions under which a configuration may become the research
candidate for a symbol — beating the incumbent, out-of-sample survival,
parameter sensitivity, cost stress. Per symbol: a filter that helps one
symbol is not adopted elsewhere.
''')


_RULES_TEMPLATE = Template('''\
"""$title $version rules skeleton — GENERATED, contains no logic yet.

Write the logic from the spec (``$spec_document``) into the two hooks below,
then delete the guard raise in ``signals_from_zone_events_${strategy_id}_$version``.
Until then every entry point raises ``NotImplementedError``: a skeleton that
returned ``[]`` instead would look exactly like a strategy that found no
trades, and a false negative result is worse than a crash.

Per the research workflow, the audit rules
(``audit_rules_${strategy_id}_$version``) are written by a different author,
from the spec alone, and never import this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_causal_loop import (
    ReactionContext,
    signals_from_zone_events,
)
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    ZoneEvent,
    build_one_hour_indicator,
    strategy_04_v0_3_parameters,
)
from ai_trade.strategy_04_v1 import Strategy04SignalResult, _TimelineZone
from ai_trade.strategy_04_v1_1 import Strategy04V11ExecutionParameters

_NOT_IMPLEMENTED = (
    "src/ai_trade/${strategy_id}_$version.py is a generated skeleton: implement "
    "_reaction_filter and _extra_columns from $spec_document, then delete the "
    "two guard raises in signals_from_zone_events_${strategy_id}_$version and "
    "candidate_signals_${strategy_id}_$version"
)


@dataclass(frozen=True)
class ${camel}V1ExecutionParameters(Strategy04V11ExecutionParameters):
    """$version tunables. TODO: add this version's parameters; every rule the
    spec makes switchable needs its own enable flag so the ablation can
    attribute effects."""


def _reaction_filter(zone: _TimelineZone, context: ReactionContext) -> bool:
    """Return False to reject a reaction. Runs inside zone matching, so a
    rejected reaction never consumes its zone."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def _extra_columns(
    selected: _TimelineZone, context: ReactionContext
) -> Dict[str, object]:
    """Record every rule's decision value at decision time, even when the rule
    is off — the independent audit re-derives decisions from these columns."""
    raise NotImplementedError(_NOT_IMPLEMENTED)


def signals_from_zone_events_${strategy_id}_$version(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    events: Iterable[ZoneEvent],
    params: ${camel}V1ExecutionParameters = ${camel}V1ExecutionParameters(),
) -> list[dict[str, object]]:
    """Create causal $version signals. NOT IMPLEMENTED — see the guard below."""
    # Guard raise: the hook stubs alone are not enough, because the shared
    # loop never calls them on inputs with no matching reaction — a bare
    # skeleton would return [] and masquerade as a valid negative result.
    # Delete this raise only once the hooks above implement the spec.
    raise NotImplementedError(_NOT_IMPLEMENTED)
    return signals_from_zone_events(  # unreachable until the guard is deleted
        fifteen_minute_bars,
        one_hour_bars,
        events,
        params,
        reaction_filter=_reaction_filter,
        extra_columns=_extra_columns,
    )


def candidate_signals_${strategy_id}_$version(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    execution_params: ${camel}V1ExecutionParameters = ${camel}V1ExecutionParameters(),
    indicator_params: Optional[Strategy04IndicatorParameters] = None,
) -> Strategy04SignalResult:
    """Build v0.3 zones and the isolated $title $version signals."""
    # Second guard, same reason: the registry's signal_builder points here,
    # so this composed entry point must also fail loudly on ANY input —
    # including inputs that would crash or no-op before reaching the builder
    # below. Delete together with the guard above.
    raise NotImplementedError(_NOT_IMPLEMENTED)
    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    indicator = build_one_hour_indicator(
        hours,
        indicator_params or strategy_04_v0_3_parameters(),
    )
    signals = signals_from_zone_events_${strategy_id}_$version(
        fifteen,
        hours,
        indicator.events,
        execution_params,
    )
    return Strategy04SignalResult(signals=signals, indicator=indicator)
''')


_AUDIT_TEMPLATE = Template('''\
"""Hand-written audit rules for $title $version — GENERATED SKELETON.

This module must be written FROM THE SPEC ONLY (``$spec_document``) and must
NEVER import the strategy implementation (``${strategy_id}_$version``,
``strategy_04_causal_loop``) nor ``strategy_registry``. The audit's entire
value is independence: it re-derives every rule's decision from the recorded
CSV columns, so it can catch an implementation that misread the spec. If the
audit imports the implementation — or is written by the same author from the
implementation — the same misreading passes its own check and the audit
proves nothing. Only the standard library may be imported here, and the
authoring workflow assigns this file to a different agent than the one who
wrote the rules module.
"""

from __future__ import annotations

from typing import AbstractSet, List, Mapping

# The columns this version appends beyond the shared signal schema. Written
# out by hand from the spec's "Producer output required for auditing" section,
# never imported from the registry — the audit must not inherit a mistake it
# is meant to find.
AUDIT_COLUMNS: tuple = ()  # TODO from $spec_document

# Ablation variant -> the rules that variant claims were active.
VARIANT_FILTERS: Mapping[str, frozenset] = {
    "base": frozenset(),
    # TODO: one entry per spec variant.
}


def audit_row(
    row: Mapping[str, str],
    enabled_filters: AbstractSet[str],
    parameters: Mapping[str, object],
) -> List[str]:
    """Check one recorded signal row against the spec's rules.

    Must return one failure string per violated rule (empty list means the
    row is clean), recomputing every decision value from ``row`` alone.
    """
    raise NotImplementedError(
        "src/ai_trade/audit_rules_${strategy_id}_$version.py is a generated "
        "skeleton: re-derive each rule's decision from the recorded CSV "
        "columns per $spec_document, importing no strategy code"
    )
''')


_REGISTRY_TEMPLATE = Template('''\
Paste into STRATEGIES in src/ai_trade/strategy_registry.py after filling every
TODO. The generator never edits the registry: the entry must land in a human-
reviewed diff. Do not delete the placeholder raise in the rules module until
its hooks are implemented from the spec.

    "$strategy_id": StrategySpec(
        strategy_id="$strategy_id",
        title="$title",
        subtitle="$subtitle",
        spec_document="$spec_document",
        versions=(
            VersionSpec(
                version_id="${strategy_id}_$version",
                strategy_id="$strategy_id",
                version_label="$version",
                incumbent="TODO",  # the version this one is measured against
                report_strategy_id="${strategy_id}_${version}_TODO_short_suffix",
                signal_builder=candidate_signals_${strategy_id}_$version,
                params_type=${camel}V1ExecutionParameters,
                indicator_version="0.3",
                variants={
                    "base": {},
                    # TODO: one variant per switchable rule, per the spec.
                },
                equity_data={},  # TODO symbol -> (15m cache, 1h cache)
                fx_data={},
                results_template="strategies/$strategy_id/$version/results/{symbol}_1h_15m_{variant}",
                audit_columns=(),  # TODO: must match the spec's audit section
                sweep_parameter="TODO",
                sweep_grid=(),  # TODO: swept, never chosen by code
                change_description="TODO ('{variant}' is substituted)",
                warning="TODO: research warning naming every in-sample parameter",
            ),
        ),
    ),

with the imports (rules module only — never import the audit module here):

    from ai_trade.${strategy_id}_$version import (
        ${camel}V1ExecutionParameters,
        candidate_signals_${strategy_id}_$version,
    )
''')


def _render(strategy_id: str, title: str, subtitle: str) -> "dict[str, str]":
    """Substitutions shared by every template."""
    return {
        "strategy_id": strategy_id,
        "camel": _camel(strategy_id),
        "title": title,
        "subtitle": subtitle,
        "version": _VERSION,
        "spec_document": f"strategies/{strategy_id}/{_VERSION}/strategy.md",
    }


def _strategy_id(value: str) -> str:
    if not _ID_PATTERN.match(value):
        raise argparse.ArgumentTypeError(
            f"--id must look like strategy_05 (got {value!r})"
        )
    return value


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold a new strategy: spec skeleton, rules-module skeleton, "
            "audit-rules skeleton, and a printed registry entry. Writes no logic."
        )
    )
    parser.add_argument("--id", type=_strategy_id, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files (default: refuse and write nothing)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="repository root to scaffold into (tests point this at a temp dir)",
    )
    args = parser.parse_args(argv)

    values = _render(args.id, args.title, args.subtitle)
    targets = {
        args.root / "strategies" / args.id / _VERSION / "strategy.md":
            _SPEC_TEMPLATE.substitute(values),
        args.root / "src" / "ai_trade" / f"{args.id}_{_VERSION}.py":
            _RULES_TEMPLATE.substitute(values),
        args.root / "src" / "ai_trade" / f"audit_rules_{args.id}_{_VERSION}.py":
            _AUDIT_TEMPLATE.substitute(values),
    }

    # All-or-nothing: the existence check runs before any write, so a refusal
    # never leaves a half-scaffolded strategy behind.
    existing = [path for path in targets if path.exists()]
    if existing and not args.force:
        for path in existing:
            print(f"refusing to overwrite {path}")
        print("nothing written; pass --force to overwrite")
        return 1

    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit newline: Path.write_text would translate to CRLF on
        # Windows, and generated Python/markdown should match the repo's LF.
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        print(f"wrote {path}")

    print()
    print(_REGISTRY_TEMPLATE.substitute(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
