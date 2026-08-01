"""Prove a refactor changed no Strategy 04 v1.2 result, byte for byte.

The committed run directories under ``strategies/strategy_04/v1_2/results``
are the reference. This script re-runs every symbol/variant into a scratch
directory and compares the produced evidence files byte for byte. Any
difference fails, loudly, naming the file.

This exists because the pipeline generalization rewrites the code that
produced those results. A refactor that "looks equivalent" is not evidence;
reproducing thirty-two committed runs exactly is. Per the research skill's
principle, a result nobody can independently verify does not exist -- and the
same applies to a claim that nothing changed.

Not a pytest test: it needs the market-data caches under ``data/``, which are
deliberately untracked, so it cannot run in a clean checkout.

Usage:
    python scripts/verify_v1_2_reproduction.py            # all 32 runs
    python scripts/verify_v1_2_reproduction.py --symbols SPY GLD
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_trade.backtest_strategy_04_v1_2_asset import SUPPORTED_SYMBOLS, VARIANTS  # noqa: E402

RESULTS_ROOT = ROOT / "strategies" / "strategy_04" / "v1_2" / "results"

# backtest_report.json is excluded on purpose: it records the run's own output
# path and would differ for a scratch directory. Everything it summarises is
# derived from the five files below, so comparing those is the stronger check.
COMPARED_FILES = (
    "candidate_signals.csv",
    "fixed_trades.csv",
    "fixed_summary.json",
    "rrms_trades.csv",
    "rrms_summary.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_one(symbol: str, variant: str, destination: Path, runner: str) -> None:
    subprocess.run(
        [
            sys.executable, "-m", runner,
            "--symbol", symbol,
            "--variant", variant,
            "--output", str(destination),
            "--skip-publish",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def compare(symbol: str, variant: str, produced: Path) -> list[str]:
    """Return a failure line per file that differs from the committed run."""
    reference = RESULTS_ROOT / f"{symbol.lower()}_1h_15m_{variant}"
    if not reference.is_dir():
        return [f"{symbol}/{variant}: no committed run at {reference}"]
    failures = []
    for name in COMPARED_FILES:
        reference_file, produced_file = reference / name, produced / name
        if not produced_file.is_file():
            failures.append(f"{symbol}/{variant}: {name} was not produced")
            continue
        if not reference_file.is_file():
            failures.append(f"{symbol}/{variant}: {name} missing from the committed run")
            continue
        if _sha256(produced_file) != _sha256(reference_file):
            failures.append(f"{symbol}/{variant}: {name} DIFFERS from the committed run")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", nargs="+", choices=SUPPORTED_SYMBOLS,
                        default=SUPPORTED_SYMBOLS)
    parser.add_argument("--variants", nargs="+", choices=tuple(VARIANTS),
                        default=tuple(VARIANTS))
    parser.add_argument("--runner", default="ai_trade.backtest_strategy_04_v1_2_asset",
                        help="Module to re-run; point this at a replacement runner.")
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="v1_2_reproduction_"))
    failures: list[str] = []
    total = len(args.symbols) * len(args.variants)
    try:
        for number, (symbol, variant) in enumerate(
            ((s, v) for s in args.symbols for v in args.variants), start=1
        ):
            destination = scratch / f"{symbol.lower()}_{variant}"
            print(f"[{number}/{total}] {symbol}/{variant}", flush=True)
            try:
                _run_one(symbol, variant, destination, args.runner)
            except subprocess.CalledProcessError as error:
                failures.append(f"{symbol}/{variant}: runner exited {error.returncode}")
                continue
            failures.extend(compare(symbol, variant, destination))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\nREPRODUCTION FAILED -- {len(failures)} difference(s):", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"\nReproduced {total} run(s) byte for byte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
