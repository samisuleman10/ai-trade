"""Backfill visualization bundles for backtest results already on disk.

This is the second stage described in
``docs/design/strategy_visualization/shared/architecture_and_data_contract.md``:
Task 1 (``visualization_contract``) knows how to validate and publish a
bundle for a single result directory. This module finds every existing
result directory across every strategy and publishes one bundle each, so
historical work becomes visible to the dashboard without anyone hand-editing
a single file.

Every result directory is independent. A bad or unexpected one is recorded
as a skip with an explicit reason and never aborts the run -- the whole
point of a backfill over 49 directories accumulated by hand over months is
that some of them will be malformed, incomplete, or surprising.

bundle_id vs. run_id
---------------------
``run_id`` is the human-readable result directory name (e.g.
``spy_1h_15m``) and is kept for display. It is NOT usable as a catalog key:
measured on this repository, 49 result directories share only 40 unique
basenames (every Strategy 04 result directory, for one, is named after its
symbol under both ``v1/`` and ``v1_1/``). A bundle_id derived from run_id
would silently collide and drop runs from the catalog with no error.
``bundle_id_for`` instead derives an identifier from the full path of the
result directory relative to the repository root, which is unique by
construction and stable across re-runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ai_trade.visualization_contract import (
    ContractError,
    build_performance,
    build_trade_ledger,
    publish_bundle,
)

# Repository root: this file lives at <repo>/src/ai_trade/<this file>.
REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = ("fixed_trades.csv", "fixed_summary.json")
REPORT_FILENAME = "backtest_report.json"
BUNDLE_DIRNAME = "visualization"

_VERSION_SEGMENT_RE = re.compile(r"^v[0-9_]+$")
_SLUG_UNSAFE_RE = re.compile(r"[\\/.:]+")
_MODE_ALIASES = {"historical_backtest_only": "historical_backtest"}


def discover_results(roots: Sequence[Any]) -> List[Path]:
    """Find every directory under ``roots`` holding both required files.

    A directory qualifies when it directly contains ``fixed_trades.csv``
    AND ``fixed_summary.json``. Directories named ``visualization`` (a
    published bundle, from either this run or a previous one) are never
    treated as a result and are not descended into, so re-running the
    backfill never mistakes its own output for a new result. Returns a
    sorted list so output order is deterministic.
    """

    found: List[Path] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            if BUNDLE_DIRNAME in dirnames:
                dirnames.remove(BUNDLE_DIRNAME)
            current = Path(dirpath)
            if current.name == BUNDLE_DIRNAME:
                continue
            if all((current / name).is_file() for name in REQUIRED_FILES):
                found.append(current)
    found.sort()
    return found


def _find_symbol(report: Dict[str, Any]) -> Optional[Any]:
    """Look up the traded symbol from the shapes actually seen in reports.

    Real ``backtest_report.json`` files place ``symbol`` in different
    spots depending on which strategy produced them: top-level for
    Strategy 04, nested under ``data`` for Strategies 02/03, and nested
    under ``research_profile`` for Strategy 01's v3-v5 runs. All three are
    read directly from the SAME report -- this is not path-based guessing,
    it is checking the plausible places the producer already put the
    value. A handful of legacy Strategy 01 reports have no symbol field
    anywhere; those legitimately resolve to ``None``.
    """

    if report.get("symbol"):
        return report["symbol"]
    data = report.get("data")
    if isinstance(data, dict) and data.get("symbol"):
        return data["symbol"]
    research_profile = report.get("research_profile")
    if isinstance(research_profile, dict) and research_profile.get("symbol"):
        return research_profile["symbol"]
    return None


def _nearest_version_segment(result_dir: Path) -> str:
    for candidate in (result_dir, *result_dir.parents):
        if _VERSION_SEGMENT_RE.match(candidate.name):
            return candidate.name
    return "unknown"


def run_identity(result_dir: Any) -> Optional[Dict[str, Any]]:
    """Read run identity from ``backtest_report.json``. Never from the path.

    Returns ``None`` when the report is missing, unreadable, or lacks a
    ``strategy_id`` -- that is the one field this function insists on;
    everything else degrades gracefully (``symbol`` may be ``None``,
    ``strategy_version`` falls back to a path segment or ``"unknown"``).
    """

    result_dir = Path(result_dir)
    report_path = result_dir / REPORT_FILENAME
    if not report_path.is_file():
        return None
    try:
        with report_path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None

    strategy_id = report.get("strategy_id")
    if not strategy_id:
        return None

    strategy_version = report.get("strategy_version") or _nearest_version_segment(result_dir)

    mode = report.get("mode")
    mode = _MODE_ALIASES.get(mode, mode)

    return {
        "run_id": result_dir.name,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "symbol": _find_symbol(report),
        "mode": mode,
    }


def bundle_id_for(result_dir: Any, repo_root: Any = REPO_ROOT) -> str:
    """Derive a catalog-unique bundle_id from a result directory's path.

    The id is the directory's path relative to ``repo_root``, with path
    separators and dots collapsed to underscores. Two distinct result
    directories always have distinct paths, so this is unique by
    construction -- unlike a run_id taken from the directory basename
    alone, which collides whenever two versions share a result folder
    name (see module docstring).

    ``result_dir`` need not actually live under ``repo_root`` (tests use
    arbitrary ``tmp_path`` locations): when it doesn't, the resolved
    absolute path is slugged instead, which is still deterministic and
    unique, just not repo-root-relative.
    """

    resolved_dir = Path(result_dir).resolve()
    resolved_root = Path(repo_root).resolve()
    try:
        relative = resolved_dir.relative_to(resolved_root)
        text = str(relative)
    except ValueError:
        text = str(resolved_dir)

    slug = _SLUG_UNSAFE_RE.sub("_", text)
    slug = slug.strip("_")
    return slug


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _required_float(summary: Dict[str, Any], field: str) -> float:
    value = summary.get(field)
    if value is None:
        raise ContractError(
            f"summary has no {field!r}; the run's starting equity cannot be recovered from it"
        )
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"summary field {field!r} is not a number: {value!r}") from exc


def _starting_equity(summary: Dict[str, Any]) -> float:
    """Recover the equity a run started with from its own summary.

    Neither ``fixed_summary.json`` nor ``fixed_trades.csv`` records a
    starting balance directly, but ``net_pnl`` is defined as the change
    from start to end, so ``ending_equity - net_pnl`` recovers it exactly
    -- this is reading the producer's own arithmetic, not inventing a
    default. When there are no trades, this correctly yields
    ``ending_equity`` itself.

    Both fields are therefore required. They used to default to 0.0, which
    turned a missing ``ending_equity`` into a published equity anchor of
    ``-net_pnl`` -- a fabricated number presented as the producer's own.
    A missing ``net_pnl`` was quieter but no better: it reported the run as
    having started exactly where it ended. Raising ``ContractError``
    instead means ``backfill`` skips the directory and records why, which
    is the honest outcome for a summary that cannot answer the question.
    """

    return _required_float(summary, "ending_equity") - _required_float(summary, "net_pnl")


def _build_variant_datasets(result_dir: Path, variant: str, run_id: str) -> List[Any]:
    rows = _read_csv_rows(result_dir / f"{variant}_trades.csv")
    summary = _read_json(result_dir / f"{variant}_summary.json")
    starting_equity = _starting_equity(summary)
    ledger = build_trade_ledger(rows, variant, run_id)
    performance = build_performance(rows, summary, variant, starting_equity)
    return [ledger, performance]


def backfill(roots: Sequence[Any], dry_run: bool) -> Dict[str, Any]:
    """Publish a visualization bundle for every discovered result directory.

    Always builds the ``fixed`` variant's datasets, and additionally the
    ``rrms`` variant's when both ``rrms_trades.csv`` and
    ``rrms_summary.json`` exist. Unless ``dry_run``, calls
    ``publish_bundle`` for each; a dry run still builds and validates
    every dataset (so validation failures show up in the report) but
    writes nothing to disk.

    A directory that cannot be resolved to an identity, or that fails
    contract validation, or that raises any other error while being
    read, is counted as skipped with a recorded reason -- never allowed
    to abort the run.
    """

    published = 0
    skipped = 0
    reasons: Dict[str, str] = {}

    for result_dir in discover_results(roots):
        key = str(result_dir)
        try:
            identity = run_identity(result_dir)
            if identity is None:
                skipped += 1
                reasons[key] = f"no valid {REPORT_FILENAME} (missing, unparseable, or lacking strategy_id)"
                continue

            run_id = identity["run_id"]
            datasets = _build_variant_datasets(result_dir, "fixed", run_id)
            variants = ["fixed"]

            has_rrms = (result_dir / "rrms_trades.csv").is_file() and (result_dir / "rrms_summary.json").is_file()
            if has_rrms:
                datasets.extend(_build_variant_datasets(result_dir, "rrms", run_id))
                variants.append("rrms")

            publish_identity = dict(identity)
            publish_identity["bundle_id"] = bundle_id_for(result_dir)
            capabilities = {"sizing_variants": variants}

            if not dry_run:
                publish_bundle(result_dir, publish_identity, datasets, capabilities, [])

            published += 1
        except ContractError as exc:
            skipped += 1
            reasons[key] = str(exc)
        except Exception as exc:  # noqa: BLE001 - one bad directory must never abort the run
            skipped += 1
            reasons[key] = f"{type(exc).__name__}: {exc}"

    return {"published": published, "skipped": skipped, "reasons": reasons}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish visualization bundles for existing backtest result directories."
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        default=None,
        help="Root directory to search for results (repeatable). Defaults to 'outputs' and 'strategies'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be published without writing anything.",
    )
    args = parser.parse_args(argv)

    roots = [Path(root) for root in args.roots] if args.roots else [REPO_ROOT / "outputs", REPO_ROOT / "strategies"]

    report = backfill(roots, dry_run=args.dry_run)
    print(f"published={report['published']} skipped={report['skipped']}")
    for path, reason in sorted(report["reasons"].items()):
        print(f"SKIPPED {path}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
