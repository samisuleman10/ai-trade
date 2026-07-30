"""Verify Strategy 04 v1.2 outputs from recorded evidence.

Two independent checks, both required by the v1.2 spec:

1. Column audit (every variant): recompute ``risk_zone_ratio`` from the
   recorded trigger close, stop and zone bounds, and confirm the recorded
   one-hour reference open/close match the actual bar identified by
   ``one_hour_atr_timestamp`` in the one-hour cache. The filters are only
   auditable if these recorded values are trustworthy.
2. Base parity (v1.2-base only): the base variant must reproduce the
   committed v1.1 run exactly -- identical candidate signals (ignoring the
   three new columns, which v1.1 lacked) and identical fixed trades. Per
   the spec, if parity fails the harness is wrong and no other v1.2 result
   may be read.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_trade.strategy_01 import load_ohlcv_csv

NEW_COLUMNS = ("risk_zone_ratio", "one_hour_reference_open", "one_hour_reference_close")
_UTC = "%Y-%m-%dT%H:%M:%SZ"
_RELATIVE_TOLERANCE = 1e-9


def _read_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def audit_columns(results_dir: Path, one_hour_csv: Path) -> dict:
    """Recompute the three v1.2 audit columns from recorded evidence."""
    rows = _read_rows(Path(results_dir) / "candidate_signals.csv")
    bars_by_timestamp = {bar.timestamp: bar for bar in load_ohlcv_csv(Path(one_hour_csv))}
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
        close_time = datetime.strptime(row["one_hour_atr_timestamp"], _UTC).replace(
            tzinfo=timezone.utc
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
        (Path(results_dir) / "fixed_trades.csv").read_text(encoding="utf-8")
        == (Path(v1_1_dir) / "fixed_trades.csv").read_text(encoding="utf-8")
    )
    return {
        "v1_2_signal_count": len(v12_signals),
        "v1_1_signal_count": len(v11_signals),
        "signals_match": signals_match,
        "trades_match": trades_match,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Strategy 04 v1.2 recorded evidence.")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--one-hour", required=True, type=Path)
    parser.add_argument("--v1-1", type=Path, default=None)
    args = parser.parse_args()

    report: dict = {"results_dir": str(args.results), "column_audit": audit_columns(args.results, args.one_hour)}
    ok = not report["column_audit"]["failures"]
    if args.v1_1 is not None:
        report["parity"] = parity_against_v1_1(args.results, args.v1_1)
        ok = ok and report["parity"]["signals_match"] and report["parity"]["trades_match"]
    report["passed"] = ok
    (args.results / "verification_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
