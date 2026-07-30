"""Verify Strategy 04 v1.2 outputs from recorded evidence.

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

Both checks are vacuously satisfiable by an empty ``candidate_signals.csv``
(zero rows trivially pass every per-row check, and empty-vs-empty parity
trivially matches). ``main()`` closes that hole: it requires at least one
audited row, and when a v1.1 comparison is requested, at least one v1.1
signal too.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ai_trade.strategy_01 import load_ohlcv_csv

NEW_COLUMNS = ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")
_UTC = "%Y-%m-%dT%H:%M:%SZ"
_RELATIVE_TOLERANCE = 1e-9

VARIANT_FILTERS: dict[str, frozenset[str]] = {
    "base": frozenset(),
    "a": frozenset({"a"}),
    "b": frozenset({"b"}),
    "ab": frozenset({"a", "b"}),
}


def _read_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def audit_columns(
    results_dir: Path,
    one_hour_csv: Path,
    enabled_filters: Optional[set[str]] = None,
    max_risk_zone_ratio: Optional[float] = None,
) -> dict:
    """Recompute the three v1.2 audit columns from recorded evidence.

    ``enabled_filters`` (a subset of ``{"a", "b"}``) is optional: when given,
    each row is additionally checked against the filter(s) the variant
    claims were active, using the recorded ``risk_zone_ratio`` /
    ``one_hour_reference_open`` / ``one_hour_reference_close`` values (not a
    recomputation -- those are already audited above).
    """
    rows = _read_rows(Path(results_dir) / "candidate_signals.csv")
    bars_by_timestamp = {bar.timestamp: bar for bar in load_ohlcv_csv(Path(one_hour_csv))}
    enabled_filters = enabled_filters or set()
    failures: list[str] = []
    for number, row in enumerate(rows, start=1):
        width = float(row["zone_upper"]) - float(row["zone_lower"])
        expected_ratio = (
            math.inf
            if width <= 0
            else abs(float(row["trigger_close"]) - float(row["stop_reference"])) / width
        )
        recorded_ratio = float(row["risk_zone_ratio"])
        if not math.isclose(recorded_ratio, expected_ratio, rel_tol=_RELATIVE_TOLERANCE):
            failures.append(
                f"row {number}: risk_zone_ratio recorded {recorded_ratio} != recomputed {expected_ratio}"
            )
        # one_hour_atr_timestamp is the reference bar's CLOSE time; the bar
        # itself is stamped one hour earlier.
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
        bar_stamp = (close_time - timedelta(hours=1)).strftime(_UTC)
        bar = bars_by_timestamp.get(bar_stamp)
        if bar is None:
            failures.append(f"row {number}: no one-hour bar at {bar_stamp} for the recorded reference")
            continue
        if not (
            math.isclose(float(row["one_hour_reference_open"]), bar.open, rel_tol=_RELATIVE_TOLERANCE)
            and math.isclose(float(row["one_hour_reference_close"]), bar.close, rel_tol=_RELATIVE_TOLERANCE)
        ):
            failures.append(
                f"row {number}: recorded reference open/close "
                f"({row['one_hour_reference_open']}, {row['one_hour_reference_close']}) "
                f"!= bar at {bar_stamp} ({bar.open}, {bar.close})"
            )
        if "a" in enabled_filters and max_risk_zone_ratio is not None:
            if recorded_ratio > max_risk_zone_ratio:
                failures.append(
                    f"row {number}: filter A violated -- risk_zone_ratio {recorded_ratio} "
                    f"> max_risk_zone_ratio {max_risk_zone_ratio}"
                )
        if "b" in enabled_filters:
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
                    f"row {number}: filter B violated -- {side} side direction disagrees with "
                    f"reference bar (open {reference_open}, close {reference_close})"
                )
    return {"rows": len(rows), "failures": failures}


def parity_against_v1_1(results_dir: Path, v1_1_dir: Path) -> dict:
    """Diff v1.2-base outputs against the committed v1.1 run."""
    v12_signals = _read_rows(Path(results_dir) / "candidate_signals.csv")
    v11_signals = _read_rows(Path(v1_1_dir) / "candidate_signals.csv")
    stripped = [
        {key: value for key, value in row.items() if key not in NEW_COLUMNS}
        for row in v12_signals
    ]
    signals_match = stripped == v11_signals
    trades_match = (
        (Path(results_dir) / "fixed_trades.csv").read_bytes()
        == (Path(v1_1_dir) / "fixed_trades.csv").read_bytes()
    )
    return {
        "v1_2_signal_count": len(v12_signals),
        "v1_1_signal_count": len(v11_signals),
        "signals_match": signals_match,
        "trades_match": trades_match,
        # Empty-vs-empty trivially matches; that must not be treated as
        # parity confirmation, so callers gate on this too.
        "non_empty": len(v11_signals) > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Strategy 04 v1.2 recorded evidence.")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--one-hour", required=True, type=Path)
    parser.add_argument("--v1-1", type=Path, default=None)
    parser.add_argument("--variant", choices=("base", "a", "b", "ab"), default=None)
    parser.add_argument("--max-risk-zone-ratio", type=float, default=2.5)
    args = parser.parse_args()

    enabled_filters = VARIANT_FILTERS.get(args.variant or "base", frozenset())
    column_audit = audit_columns(
        args.results, args.one_hour,
        enabled_filters=enabled_filters,
        max_risk_zone_ratio=args.max_risk_zone_ratio,
    )
    report: dict = {"results_dir": str(args.results), "column_audit": column_audit}
    ok = column_audit["rows"] > 0 and not column_audit["failures"]
    if args.v1_1 is not None:
        report["parity"] = parity_against_v1_1(args.results, args.v1_1)
        ok = (
            ok
            and report["parity"]["signals_match"]
            and report["parity"]["trades_match"]
            and report["parity"]["non_empty"]
        )
    report["passed"] = ok
    (args.results / "verification_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
