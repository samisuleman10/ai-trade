"""Generic scaffolding for verifying a strategy version's recorded evidence.

This module holds only the checks that are valid for ANY version: row
iteration, the causality check (the reference bar must have closed at or
before the decision), the recorded-vs-actual reference open/close check,
parity diffing against an incumbent with the version's audit columns
stripped, the vacuous-pass guards, report writing and the exit code.

What it deliberately does NOT hold is the version-specific predicate ("a row
claiming Filter A passed must satisfy Filter A"). That lives in a
hand-written audit-rules module (e.g. ``audit_rules_v1_2``) that is passed in
as the ``audit_row`` callable and imports no strategy code. The split exists
to protect the audit's one source of value: it re-derives decisions from
recorded CSV columns and never asks the implementation, so it can catch a
bug the implementation and a code-generated audit would share.

Vacuous passes are the scaffolding's problem, not the rules': zero audited
rows must fail, and an empty incumbent must fail, because an empty CSV
trivially satisfies every per-row rule and empty-vs-empty parity trivially
matches. ``finalize_report`` closes both holes.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AbstractSet, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ai_trade.strategy_01 import load_ohlcv_csv

_UTC = "%Y-%m-%dT%H:%M:%SZ"
# Recorded floats survive a text round-trip through the CSV; equality up to
# relative rounding noise is the strongest claim a comparison can make.
_RELATIVE_TOLERANCE = 1e-9


def read_rows(path: Path) -> List[Dict[str, str]]:
    """Read a CSV as dict rows; a blank file is zero rows, not an error.

    Zero rows must reach the caller as a countable fact (so the vacuous-pass
    guard can reject it) rather than blowing up on a missing header.
    """
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def audit_recorded_rows(
    results_dir: Path,
    one_hour_csv: Path,
    audit_row: Callable[[Mapping[str, str], AbstractSet[str], Mapping[str, object]], List[str]],
    enabled_filters: Optional[AbstractSet[str]] = None,
    parameters: Optional[Mapping[str, object]] = None,
    reference_columns: Optional[Tuple[str, str]] = (
        "one_hour_reference_open",
        "one_hour_reference_close",
    ),
    reference_bar_length: timedelta = timedelta(hours=1),
) -> dict:
    """Audit every recorded candidate signal from evidence alone.

    Generic checks (causality, reference-bar fidelity) run here; everything
    version-specific is delegated to ``audit_row``, which returns one failure
    string per violated rule for a single row. ``reference_columns`` may be
    ``None`` for a version that records no reference open/close.
    """
    rows = read_rows(Path(results_dir) / "candidate_signals.csv")
    bars_by_timestamp = {bar.timestamp: bar for bar in load_ohlcv_csv(Path(one_hour_csv))}
    enabled_filters = enabled_filters or frozenset()
    parameters = parameters or {}
    failures: List[str] = []
    for number, row in enumerate(rows, start=1):
        # Version-specific rules first: they read only the row itself, so
        # they can report even when the reference bar turns out to be missing.
        failures.extend(
            f"row {number}: {failure}"
            for failure in audit_row(row, enabled_filters, parameters)
        )
        # Causality: the timestamp names the reference bar's CLOSE time; a
        # close after the decision means the strategy peeked at the future.
        decision_time = datetime.strptime(row["decision_timestamp"], _UTC).replace(
            tzinfo=timezone.utc
        )
        close_time = datetime.strptime(row["one_hour_atr_timestamp"], _UTC).replace(
            tzinfo=timezone.utc
        )
        if close_time > decision_time:
            failures.append(
                f"row {number}: not causal -- reference bar close "
                f"{row['one_hour_atr_timestamp']} is after decision_timestamp "
                f"{row['decision_timestamp']}"
            )
        # The bar itself is stamped by its OPEN, one bar-length before the close.
        bar_stamp = (close_time - reference_bar_length).strftime(_UTC)
        bar = bars_by_timestamp.get(bar_stamp)
        if bar is None:
            failures.append(
                f"row {number}: no one-hour bar at {bar_stamp} for the recorded reference"
            )
            continue
        if reference_columns is not None:
            # The recorded open/close must match the actual cached bar: the
            # per-version filter checks read these recorded values, so they
            # are only meaningful if this fidelity check holds.
            open_column, close_column = reference_columns
            if not (
                math.isclose(float(row[open_column]), bar.open, rel_tol=_RELATIVE_TOLERANCE)
                and math.isclose(float(row[close_column]), bar.close, rel_tol=_RELATIVE_TOLERANCE)
            ):
                failures.append(
                    f"row {number}: recorded reference open/close "
                    f"({row[open_column]}, {row[close_column]}) "
                    f"!= bar at {bar_stamp} ({bar.open}, {bar.close})"
                )
    return {"rows": len(rows), "failures": failures}


def parity_against_incumbent(
    results_dir: Path,
    incumbent_dir: Path,
    audit_columns: Sequence[str],
    candidate_label: str = "candidate",
    incumbent_label: str = "incumbent",
) -> dict:
    """Diff this version's outputs against the committed incumbent run.

    ``audit_columns`` (the columns this version added, which the incumbent
    lacks) are stripped before comparing signals. The labels shape the report
    keys (``v1_2_signal_count`` etc.) so committed report files keep their
    historical field names.
    """
    candidate_signals = read_rows(Path(results_dir) / "candidate_signals.csv")
    incumbent_signals = read_rows(Path(incumbent_dir) / "candidate_signals.csv")
    stripped = [
        {key: value for key, value in row.items() if key not in audit_columns}
        for row in candidate_signals
    ]
    signals_match = stripped == incumbent_signals
    trades_match = (
        (Path(results_dir) / "fixed_trades.csv").read_bytes()
        == (Path(incumbent_dir) / "fixed_trades.csv").read_bytes()
    )
    return {
        f"{candidate_label}_signal_count": len(candidate_signals),
        f"{incumbent_label}_signal_count": len(incumbent_signals),
        "signals_match": signals_match,
        "trades_match": trades_match,
        # Empty-vs-empty trivially matches; that must not be treated as
        # parity confirmation, so callers gate on this too.
        "non_empty": len(incumbent_signals) > 0,
    }


def finalize_report(
    results_dir: Path,
    column_audit: dict,
    parity: Optional[dict] = None,
) -> int:
    """Write ``verification_report.json``, print it, return the exit code.

    The pass verdict lives here so every version shares the same vacuous-pass
    guards: zero audited rows fail (an empty CSV satisfies every per-row rule
    vacuously), and when parity was requested, an empty incumbent fails too.
    """
    report: dict = {"results_dir": str(results_dir), "column_audit": column_audit}
    ok = column_audit["rows"] > 0 and not column_audit["failures"]
    if parity is not None:
        report["parity"] = parity
        ok = ok and parity["signals_match"] and parity["trades_match"] and parity["non_empty"]
    report["passed"] = ok
    (Path(results_dir) / "verification_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if ok else 1
