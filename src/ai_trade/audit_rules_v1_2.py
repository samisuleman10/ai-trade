"""Hand-written audit rules for Strategy 04 v1.2, independent of the code they audit.

This module re-derives the v1.2 filter decisions from recorded CSV columns
alone, straight from the v1.2 spec. It deliberately imports NOTHING from the
strategy implementation (``strategy_04_v1_2``, ``strategy_04_causal_loop``,
``strategy_04_v1_1``) nor from ``strategy_registry``: an audit that asks the
implementation whether the implementation was right proves nothing. If the
implementation misreads the spec, an independent re-derivation is what
catches it -- so every quantity below is recomputed here by hand, even where
the strategy module has a function that "already does that".

``tests/test_verify_strategy_04_v1_2.py`` enforces the import ban
mechanically with ``ast``; this docstring only explains why the ban exists.
"""

from __future__ import annotations

import math
from typing import AbstractSet, List, Mapping

# The columns v1.2 appends beyond the shared v1.1 signal schema. Written out
# by hand from the spec rather than imported from the registry, for the same
# independence reason: the audit must not inherit a mistake it is meant to find.
AUDIT_COLUMNS = (
    "risk_zone_ratio",
    "one_hour_reference_open",
    "one_hour_reference_close",
)

# Ablation variant -> the rejection filters that variant claims were active.
VARIANT_FILTERS: Mapping[str, frozenset] = {
    "base": frozenset(),
    "a": frozenset({"a"}),
    "b": frozenset({"b"}),
    "ab": frozenset({"a", "b"}),
}

# Recorded floats survive a text round-trip through the CSV; equality up to
# relative rounding noise is the strongest claim a recomputation can make.
_RELATIVE_TOLERANCE = 1e-9


def audit_row(
    row: Mapping[str, str],
    enabled_filters: AbstractSet[str],
    parameters: Mapping[str, object],
) -> List[str]:
    """Check one recorded signal row against the v1.2 spec's filter rules.

    Returns one failure string per violated rule (empty list means the row is
    clean). ``parameters`` carries the variant's tunables; v1.2 has exactly
    one, ``max_risk_zone_ratio``, and a ``None`` value skips the Filter A
    threshold check (the recompute of the ratio itself always runs).
    """
    failures: List[str] = []

    # Spec: risk_zone_ratio = |trigger_close - stop_reference| / zone width.
    # A degenerate zone (zero or negative width) is infinitely risky, so it
    # can never satisfy Filter A -- hence math.inf, not a division error.
    width = float(row["zone_upper"]) - float(row["zone_lower"])
    expected_ratio = (
        math.inf
        if width <= 0
        else abs(float(row["trigger_close"]) - float(row["stop_reference"])) / width
    )
    recorded_ratio = float(row["risk_zone_ratio"])
    if not math.isclose(recorded_ratio, expected_ratio, rel_tol=_RELATIVE_TOLERANCE):
        failures.append(
            f"risk_zone_ratio recorded {recorded_ratio} != recomputed {expected_ratio}"
        )

    max_risk_zone_ratio = parameters.get("max_risk_zone_ratio")
    if "a" in enabled_filters and max_risk_zone_ratio is not None:
        # Filter A: a surviving row must sit within the threshold. Checked
        # against the RECORDED ratio -- its fidelity was just established above.
        if recorded_ratio > float(max_risk_zone_ratio):  # type: ignore[arg-type]
            failures.append(
                f"filter A violated -- risk_zone_ratio {recorded_ratio} "
                f"> max_risk_zone_ratio {max_risk_zone_ratio}"
            )

    if "b" in enabled_filters:
        # Filter B: the trade side must agree with the latest completed
        # one-hour candle's direction (long needs close >= open, short the
        # reverse). Uses the recorded reference open/close, whose fidelity
        # against the actual bar the generic shell audits separately.
        reference_open = float(row["one_hour_reference_open"])
        reference_close = float(row["one_hour_reference_close"])
        side = row["side"]
        agrees = (
            reference_close >= reference_open
            if side == "long"
            else reference_close <= reference_open
        )
        if not agrees:
            failures.append(
                f"filter B violated -- {side} side direction disagrees with "
                f"reference bar (open {reference_open}, close {reference_close})"
            )

    return failures
