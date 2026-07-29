"""Publish a visualization bundle for a single, already-written result directory.

This closes the loop described in
``docs/design/strategy_visualization/shared/architecture_and_data_contract.md``:
Task 2 (``backfill_visualization_bundles``) walks a tree of historical result
directories and publishes a bundle for each. This module reuses the exact
same identity and dataset-building helpers, but for exactly one directory --
the one a backtest run just finished writing -- so a live run can publish
its own bundle the moment it completes, with no backfill pass required.

Publication must never destroy or obscure a completed backtest's real
output. Every failure mode -- missing required files, an unreadable or
incomplete ``backtest_report.json``, a contract violation, or anything else
-- is caught here and turned into a ``None`` return plus a printed warning.
Nothing in this module raises into its caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ai_trade.backfill_visualization_bundles import (
    REQUIRED_FILES,
    _build_variant_datasets,
    bundle_id_for,
    run_identity,
)
from ai_trade.ledger_audit_datasets import ledger_audit_entries, merge_audit_datasets
from ai_trade.visualization_contract import publish_bundle


def publish_result_directory(result_dir: Any) -> Optional[Path]:
    """Publish a visualization bundle for ``result_dir``, or return ``None``.

    Mirrors ``backfill()``'s per-directory logic (same required-files
    check, same ``run_identity``/``bundle_id_for``/dataset-building
    helpers, same optional ``rrms`` variant), but for a single directory
    supplied directly by a caller rather than discovered by walking a
    tree.

    Returns ``None`` -- after printing a warning describing why -- when:
    ``result_dir`` lacks ``fixed_trades.csv`` or ``fixed_summary.json``;
    its ``backtest_report.json`` is missing, unparseable, or lacks a
    ``strategy_id``; or building/publishing the bundle raises for any
    other reason (a malformed row, a contract violation, an I/O error).
    This function never raises: a failed export must never destroy or
    obscure a completed backtest's already-written artifacts.
    """

    result_dir = Path(result_dir)
    try:
        missing = [name for name in REQUIRED_FILES if not (result_dir / name).is_file()]
        if missing:
            print(f"WARNING: skipping visualization publish for {result_dir}: missing {missing}")
            return None

        identity = run_identity(result_dir)
        if identity is None:
            print(
                f"WARNING: skipping visualization publish for {result_dir}: "
                "no valid backtest_report.json (missing, unparseable, or lacking strategy_id)"
            )
            return None

        run_id = identity["run_id"]
        datasets = _build_variant_datasets(result_dir, "fixed", run_id)
        variants = ["fixed"]

        has_rrms = (result_dir / "rrms_trades.csv").is_file() and (result_dir / "rrms_summary.json").is_file()
        if has_rrms:
            datasets.extend(_build_variant_datasets(result_dir, "rrms", run_id))
            variants.append("rrms")

        # A live run publishes the same ledger audit the backfill does.
        # Without this, re-running a backtest would replace an audited
        # bundle with an unaudited one -- the audit would vanish from the
        # dashboard precisely when the results were freshest. The Strategy
        # 04 signal checks are not built here: they need the repository's
        # bar caches, which a single result directory cannot locate on its
        # own, so the backfill remains the place that adds them.
        datasets.extend(
            merge_audit_datasets(ledger_audit_entries(result_dir, run_id, "fixed"), [])
        )

        publish_identity = dict(identity)
        publish_identity["bundle_id"] = bundle_id_for(result_dir)
        capabilities = {
            "sizing_variants": variants,
            "has_trade_audit": True,
            "has_signal_audit": False,
        }

        return publish_bundle(result_dir, publish_identity, datasets, capabilities, [])
    except Exception as exc:  # noqa: BLE001 - a publish failure must never propagate to the caller
        print(
            f"WARNING: failed to publish visualization bundle for {result_dir}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None
