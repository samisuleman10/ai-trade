"""Run and archive deterministic historical research profiles.

This module deliberately orchestrates only read-only downloads and local
backtests. It has no broker order, account, or live-execution functionality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from ai_trade.research_profiles import PROFILES, ResearchProfile, get_profile


ROOT = Path(__file__).resolve().parents[2]


def _absolute(root: Path, relative: str) -> Path:
    return root / Path(relative)


def validate_profile_data(profile: ResearchProfile, root: Path = ROOT) -> dict[str, dict[str, object]]:
    """Load and validate the saved validation reports required by a profile."""
    data_directory = _absolute(root, profile.data_directory)
    reports: dict[str, dict[str, object]] = {}
    for filename in (profile.entry_filename, profile.trend_filename):
        csv_path = data_directory / filename
        report_path = csv_path.with_suffix(".validation.json")
        if not csv_path.is_file() or not report_path.is_file():
            raise FileNotFoundError(f"Missing required profile data or validation report: {csv_path}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not report.get("validation", {}).get("valid"):
            raise ValueError(f"Invalid market-data report: {report_path}")
        reports[filename] = report
    return reports


def refresh_profile_data(profile: ResearchProfile, *, root: Path = ROOT, port: int = 7496, client_id: int = 41) -> None:
    """Run a profile's explicitly configured, read-only historical downloader."""
    if not profile.downloader_module:
        raise ValueError(f"{profile.profile_id} has no approved downloader configured.")
    command = [
        sys.executable,
        "-m",
        profile.downloader_module,
        "--port",
        str(port),
        "--client-id",
        str(client_id),
        "--output",
        str(_absolute(root, profile.data_directory)),
        "--timeframes",
        *profile.download_timeframes,
    ]
    if profile.one_hour_duration:
        command.extend(("--one-hour-duration", profile.one_hour_duration))
    if profile.four_hour_duration:
        command.extend(("--four-hour-duration", profile.four_hour_duration))
    subprocess.run(command, cwd=root, check=True)


def _run(command: list[str], *, root: Path) -> None:
    subprocess.run(command, cwd=root, check=True)


def run_profile(
    profile: ResearchProfile,
    *,
    run_id: str,
    root: Path = ROOT,
    refresh_data: bool = False,
    port: int = 7496,
    client_id: int = 41,
) -> Path:
    """Validate inputs, run the shared backtest, and generate a trade-review visual."""
    if not profile.is_runnable:
        raise ValueError(f"{profile.profile_id} is not runnable: {profile.unavailable_reason}")
    if refresh_data:
        refresh_profile_data(profile, root=root, port=port, client_id=client_id)
    validation = validate_profile_data(profile, root)
    run_directory = root / "outputs" / "strategy_01" / profile.strategy_version / profile.symbol.lower() / "runs" / run_id
    if run_directory.exists():
        raise FileExistsError(f"Run directory already exists: {run_directory}")
    entry_path = _absolute(root, profile.data_directory) / profile.entry_filename
    trend_path = _absolute(root, profile.data_directory) / profile.trend_filename
    _run(
        [
            sys.executable,
            "-m",
            "ai_trade.backtest_strategy_01",
            "--profile",
            profile.backtest_profile,
            "--one-hour",
            str(entry_path),
            "--four-hour",
            str(trend_path),
            "--output",
            str(run_directory),
        ],
        root=root,
    )
    _run(
        [
            sys.executable,
            "scripts/generate_trade_review_visual.py",
            "--bars",
            str(entry_path),
            "--trades",
            str(run_directory / "fixed_trades.csv"),
            "--output",
            str(run_directory / "trade_review.html"),
            "--symbol",
            profile.symbol,
            "--timeframe",
            profile.entry_timeframe,
            "--review-id",
            f"{profile.profile_id}-{run_id}-review",
        ],
        root=root,
    )
    report_path = run_directory / "backtest_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["research_profile"] = asdict(profile)
    report["input_validation"] = validation
    report["run_id"] = run_id
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return run_directory


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(directory: Path) -> Iterable[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file())


def archive_run(profile: ResearchProfile, run_directory: Path, archive_directory: Path, *, root: Path = ROOT) -> Path:
    """Create an immutable, self-describing copy of a completed research run."""
    if archive_directory.exists():
        raise FileExistsError(f"Archive directory already exists: {archive_directory}")
    archive_directory.mkdir(parents=True)
    shutil.copytree(run_directory, archive_directory / "run")
    shutil.copytree(_absolute(root, profile.data_directory), archive_directory / "market_data")
    snapshot = archive_directory / "source_snapshot"
    snapshot.mkdir()
    for relative in (
        profile.strategy_document,
        "src/ai_trade/strategy_01.py",
        "src/ai_trade/backtest_strategy_01.py",
        "src/ai_trade/research_profiles.py",
        "src/ai_trade/research_pipeline.py",
        "scripts/generate_trade_review_visual.py",
    ):
        source = _absolute(root, relative)
        shutil.copy2(source, snapshot / source.name)
    manifest = {
        "profile": asdict(profile),
        "archived_run": str(run_directory.relative_to(root)),
        "files": {
            str(path.relative_to(archive_directory)): _sha256(path)
            for path in _files(archive_directory)
        },
    }
    (archive_directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return archive_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic, historical-only strategy research.")
    parser.add_argument("--profile", choices=tuple(sorted(PROFILES)), required=True)
    parser.add_argument("--run-id", required=True, help="Stable identifier; existing run IDs are never overwritten.")
    parser.add_argument("--refresh-data", action="store_true", help="Use the profile's read-only IBKR historical downloader first.")
    parser.add_argument("--port", type=int, default=7496)
    parser.add_argument("--client-id", type=int, default=41)
    parser.add_argument("--archive", type=Path, help="Optional new destination for an immutable run archive.")
    args = parser.parse_args()
    profile = get_profile(args.profile)
    run_directory = run_profile(
        profile,
        run_id=args.run_id,
        refresh_data=args.refresh_data,
        port=args.port,
        client_id=args.client_id,
    )
    print(f"Research run saved to {run_directory}")
    if args.archive:
        archive_directory = args.archive if args.archive.is_absolute() else ROOT / args.archive
        archive_run(profile, run_directory, archive_directory)
        print(f"Immutable archive saved to {archive_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
