"""Publish every run's ledger checks as the bundle's ``trade_audit`` dataset.

``strategy_04_audit_datasets`` does this for Strategy 04's rule checks and
returns nothing for any other strategy, because those checks need signal
evidence only Strategy 04 records. This module does it for the checks in
``ledger_audit``, which need nothing but the recorded ledger and therefore
run for every result directory in the repository.

There is exactly ONE ``trade_audit`` dataset per bundle. A Strategy 04 run
does not publish a second one: its signal checks are concatenated onto the
same per-trade entry by ``merge_audit_datasets``, so the dashboard reads one
dataset, one pass/fail verdict per trade, and one summary -- rather than two
audits it would have to reconcile.

This module does the I/O ``ledger_audit`` refuses to do: reading the ledger
CSV and establishing the contract multiplier.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ai_trade.ledger_audit import LedgerRow, audit_ledger
from ai_trade.visualization_contract import ContractError, Dataset, build_trade_audit

REPORT_FILENAME = "backtest_report.json"
TRADE_AUDIT_DATASET_ID = "trade_audit"

# Where a report may record the multiplier. Both are real: 36 of this
# repository's reports put it under ``assumptions`` (including every MGC
# run, at 10.0) and six put it under ``backtest_configuration`` (all 1.0).
# No report records it at the top level, and none records it twice.
MULTIPLIER_LOCATIONS = ("assumptions", "backtest_configuration")

# What an unmultiplied instrument's report looks like: it says nothing.
# Six reports record no multiplier anywhere, and all six trade equity ETFs.
DEFAULT_CONTRACT_MULTIPLIER = 1.0

# ``None`` already means "unknown, report it as inconclusive", so it cannot
# also mean "not supplied". This sentinel carries the second meaning.
READ_FROM_REPORT = object()


def load_ledger_rows(path: Any) -> List[LedgerRow]:
    """Read a trade ledger CSV into typed rows, in recorded order.

    Order is load-bearing twice over: ``equity_after`` is only checkable
    against the row before it, and trade ids are assigned by position.
    """

    rows: List[LedgerRow] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=1):
            try:
                rows.append(
                    LedgerRow(
                        decision_timestamp=row["decision_timestamp"],
                        entry_timestamp=row["entry_timestamp"],
                        exit_timestamp=row["exit_timestamp"],
                        side=row["side"],
                        quantity=int(row["quantity"]),
                        entry_price=float(row["entry_price"]),
                        stop_price=float(row["stop_price"]),
                        target_price=float(row["target_price"]),
                        exit_price=float(row["exit_price"]),
                        exit_reason=row["exit_reason"],
                        gross_pnl=float(row["gross_pnl"]),
                        costs=float(row["costs"]),
                        net_pnl=float(row["net_pnl"]),
                        result_r=float(row["result_r"]),
                        equity_after=float(row["equity_after"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ContractError(
                    "ledger row %d in %s is not readable: %s" % (index, path, exc)
                ) from exc
    return rows


def _numeric_multiplier(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number > 0:
        return None
    return number


def contract_multiplier_from_report(report: Any) -> Optional[float]:
    """The multiplier a parsed ``backtest_report.json`` states, or ``None``.

    ``None`` means "cannot be established", and callers must treat it as
    inconclusive rather than substituting a default -- see
    ``ledger_audit.check_result_r``. It is returned when the report is not
    a mapping at all, when a recorded value is not a positive number, and
    when two locations record values that disagree (one report cannot state
    two multipliers, and picking the one that makes the arithmetic work
    would be assuming the answer).

    A report that records no multiplier anywhere is a different case: that
    is how these producers state an unmultiplied instrument, so it resolves
    to 1.0. That is reading the convention, not guessing at silence --
    every one of the six such runs trades an equity ETF, and all 1,164 of
    their trades reconcile at 1.0.
    """

    if not isinstance(report, Mapping):
        return None

    found: List[float] = []
    for location in MULTIPLIER_LOCATIONS:
        block = report.get(location)
        if isinstance(block, Mapping) and "contract_multiplier" in block:
            value = _numeric_multiplier(block["contract_multiplier"])
            if value is None:
                return None
            found.append(value)
    if "contract_multiplier" in report:
        value = _numeric_multiplier(report["contract_multiplier"])
        if value is None:
            return None
        found.append(value)

    if not found:
        return DEFAULT_CONTRACT_MULTIPLIER
    if len(set(found)) > 1:
        return None
    return found[0]


def contract_multiplier_for(result_dir: Any) -> Optional[float]:
    """Read the multiplier from a result directory's report.

    Returns ``None`` when the report is absent or unparseable. That is the
    case the caller must never paper over: a run whose sizing basis cannot
    be read has not been verified, and defaulting to 1.0 would pass every
    equity run and fail every futures run with equal confidence.
    """

    report_path = Path(result_dir) / REPORT_FILENAME
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return contract_multiplier_from_report(report)


def _entry(trade_id: str, checks: Sequence[Any]) -> Dict[str, Any]:
    return {
        "trade_id": trade_id,
        "checks": [
            {
                "check_id": check.check_id,
                "passed": check.passed,
                "expected": check.expected,
                "actual": check.actual,
            }
            for check in checks
        ],
    }


def ledger_audit_entries(
    result_dir: Any,
    run_id: str,
    variant: str = "fixed",
    contract_multiplier: Any = READ_FROM_REPORT,
) -> List[Dict[str, Any]]:
    """Audit one variant's ledger and shape the result as audit entries.

    Trade ids are constructed exactly as ``build_trade_ledger`` constructs
    them -- ``<run_id>:<variant>:<six-digit ordinal>`` over the same ledger
    in the same order -- because the dashboard joins this dataset to the
    ledger on that id.

    ``contract_multiplier`` defaults to ``READ_FROM_REPORT``, meaning "read
    it from the result directory's report". Passing ``None`` explicitly
    means "unknown", which is a distinct and meaningful state, so it cannot
    double as "not supplied".
    """

    result_dir = Path(result_dir)
    if contract_multiplier is READ_FROM_REPORT:
        contract_multiplier = contract_multiplier_for(result_dir)

    rows = load_ledger_rows(result_dir / ("%s_trades.csv" % variant))
    results = audit_ledger(rows, contract_multiplier)
    return [
        _entry("%s:%s:%06d" % (run_id, variant, ordinal), checks)
        for ordinal, checks in enumerate(results, start=1)
    ]


def merge_audit_datasets(
    ledger_entries: Sequence[Mapping[str, Any]],
    signal_datasets: Sequence[Dataset],
) -> List[Dataset]:
    """Combine the ledger checks with a strategy's signal checks, if any.

    ``signal_datasets`` is whatever ``strategy_04_audit_datasets`` returned:
    empty for every other strategy, or ``[zones, trade_audit,
    audit_windows]`` for Strategy 04. Its ``trade_audit`` is folded into
    the ledger entries and rebuilt through ``build_trade_audit`` -- so the
    published ``passed`` flag and summary are derived once, from the whole
    evidence, and cannot disagree with the checks beneath them. The other
    datasets pass through untouched, in their original positions.

    A signal check naming a trade the ledger does not contain raises rather
    than being dropped: the two would then be describing different ledgers,
    and publishing the intersection would hide that.
    """

    by_trade_id = {str(entry["trade_id"]): dict(entry) for entry in ledger_entries}
    for entry in by_trade_id.values():
        entry["checks"] = list(entry.get("checks") or [])

    merged: List[Dataset] = []
    signal_audit_seen = False
    for dataset in signal_datasets:
        if dataset.dataset_id != TRADE_AUDIT_DATASET_ID:
            merged.append(dataset)
            continue
        signal_audit_seen = True
        for trade in dataset.payload.get("trades", []):
            trade_id = str(trade["trade_id"])
            entry = by_trade_id.get(trade_id)
            if entry is None:
                raise ContractError(
                    "signal audit covers trade %s, which the ledger does not contain" % trade_id
                )
            if trade.get("trigger_timestamp"):
                entry["trigger_timestamp"] = trade["trigger_timestamp"]
            entry["checks"].extend(trade.get("checks") or [])
        merged.append(build_trade_audit(list(by_trade_id.values())))

    if not signal_audit_seen:
        merged.append(build_trade_audit(list(by_trade_id.values())))
    return merged
