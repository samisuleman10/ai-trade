"""Verify Strategy 04 v1.2 outputs from recorded evidence.

Thin wrapper: the generic scaffolding (row iteration, causality check,
reference-bar fidelity, parity diffing, vacuous-pass guards, report writing)
lives in ``verify_version``; the v1.2-specific filter rules live in
``audit_rules_v1_2``, hand-written against the spec and importing no strategy
code. This module keeps the historical CLI and the exports the tests import
(``audit_columns``, ``parity_against_v1_1``, ``main``).

Two independent checks, both required by the v1.2 spec:

1. Column audit (every variant): recompute ``risk_zone_ratio`` from the
   recorded trigger close, stop and zone bounds, and confirm the recorded
   one-hour reference open/close match the actual bar identified by
   ``one_hour_atr_timestamp`` in the one-hour cache. The filters are only
   auditable if these recorded values are trustworthy. The audit also
   checks causality (the reference bar must have closed at or before the
   decision) and, when told which filters were enabled for the variant,
   that every row actually satisfies the filter it claims to have passed.
2. Base parity (v1.2-base only): the base variant must reproduce the
   committed v1.1 run exactly -- identical candidate signals (ignoring the
   three new columns, which v1.1 lacked) and identical fixed trades. Per
   the spec, if parity fails the harness is wrong and no other v1.2 result
   may be read.

Both checks are vacuously satisfiable by an empty ``candidate_signals.csv``;
``verify_version.finalize_report`` closes that hole (zero audited rows fail,
and an empty v1.1 incumbent fails when parity is requested).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from ai_trade import verify_version
from ai_trade.audit_rules_v1_2 import AUDIT_COLUMNS, VARIANT_FILTERS, audit_row

# Historical export name for the three v1.2 audit columns.
NEW_COLUMNS = AUDIT_COLUMNS

__all__ = ["NEW_COLUMNS", "VARIANT_FILTERS", "audit_columns", "parity_against_v1_1", "main"]


def audit_columns(
    results_dir: Path,
    one_hour_csv: Path,
    enabled_filters: Optional[set] = None,
    max_risk_zone_ratio: Optional[float] = None,
) -> dict:
    """Recompute the three v1.2 audit columns from recorded evidence.

    ``enabled_filters`` (a subset of ``{"a", "b"}``) is optional: when given,
    each row is additionally checked against the filter(s) the variant
    claims were active, using the recorded ``risk_zone_ratio`` /
    ``one_hour_reference_open`` / ``one_hour_reference_close`` values (not a
    recomputation -- those are already audited above).
    """
    return verify_version.audit_recorded_rows(
        results_dir,
        one_hour_csv,
        audit_row=audit_row,
        enabled_filters=enabled_filters,
        parameters={"max_risk_zone_ratio": max_risk_zone_ratio},
    )


def parity_against_v1_1(results_dir: Path, v1_1_dir: Path) -> dict:
    """Diff v1.2-base outputs against the committed v1.1 run."""
    return verify_version.parity_against_incumbent(
        results_dir,
        v1_1_dir,
        NEW_COLUMNS,
        candidate_label="v1_2",
        incumbent_label="v1_1",
    )


def main() -> int:
    # The parser stays here, not in the generic shell, so this CLI's surface
    # (flags, choices, defaults) is exactly what it was before the split.
    parser = argparse.ArgumentParser(description="Verify Strategy 04 v1.2 recorded evidence.")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--one-hour", required=True, type=Path)
    parser.add_argument("--v1-1", type=Path, default=None)
    parser.add_argument("--variant", choices=tuple(VARIANT_FILTERS), default=None)
    parser.add_argument("--max-risk-zone-ratio", type=float, default=2.5)
    args = parser.parse_args()

    enabled_filters = VARIANT_FILTERS.get(args.variant or "base", frozenset())
    column_audit = audit_columns(
        args.results, args.one_hour,
        enabled_filters=enabled_filters,
        max_risk_zone_ratio=args.max_risk_zone_ratio,
    )
    parity = (
        parity_against_v1_1(args.results, args.v1_1) if args.v1_1 is not None else None
    )
    return verify_version.finalize_report(args.results, column_audit, parity)


if __name__ == "__main__":
    raise SystemExit(main())
