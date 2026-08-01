"""Run a strategy version's full ablation grid in gate order, once.

The lifecycle in .claude/skills/strategy-research/SKILL.md is a fixed
sequence: run the base variant, prove it reproduces the incumbent, only then
run the filtered variants, verify each one's recorded evidence, sweep the
threshold, summarise, publish. Doing that by hand for eight symbols and four
variants is thirty-two runs plus twenty-nine verifications in the right
order, and the order is the safety property -- reading a filtered result
before parity is proven is exactly what the spec forbids.

This module owns the order and nothing else. Every stage shells out to the
CLI that already implements it, so each remains independently runnable and
this file contains no backtest, verification, or reporting logic. Adding a
future strategy version means adding one ``GridSpec`` to ``GRIDS``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ai_trade.run_strategy_version import symbol_run_inputs
from ai_trade.strategy_registry import VERSIONS

ROOT = Path(__file__).resolve().parents[2]

STAGES: tuple[str, ...] = ("base", "parity", "variants", "audit", "sweep", "summary", "publish")


@dataclass(frozen=True)
class GridSpec:
    """Everything needed to drive one strategy version's ablation grid."""

    grid_id: str
    # The registry entry this grid runs. Symbols, variants and result paths
    # are read from it rather than restated: a grid that disagreed with the
    # runner about which symbols exist is what left IWM, GLD and SLV out of
    # the ablation table while every run succeeded.
    version_id: str
    # CLI entry points. These stay named here because they are process
    # boundaries, not version facts -- each stage must remain independently
    # runnable, which is what keeps a failed stage debuggable on its own.
    runner_module: str
    verifier_module: str
    sweep_module: str
    summarizer_module: str
    publisher_module: str
    incumbent_results_template: str | None
    incumbent_flag: str
    incumbent_symbols: tuple[str, ...]

    @property
    def version(self):
        return VERSIONS[self.version_id]

    @property
    def symbols(self) -> tuple[str, ...]:
        return self.version.supported_symbols

    @property
    def variants(self) -> tuple[str, ...]:
        return tuple(self.version.variants)

    @property
    def results_root(self) -> str:
        """The directory holding every run of this version."""
        return str(PurePosixPath(self.version.results_template).parent)

    @property
    def base_variant(self) -> str:
        return self.variants[0]

    @property
    def filtered_variants(self) -> tuple[str, ...]:
        return self.variants[1:]

    @property
    def symbols_without_incumbent(self) -> tuple[str, ...]:
        """Symbols this version introduces, in grid order.

        These get no parity gate because there is no prior run to reproduce --
        not because the gate was waived. ``run_grid`` names them out loud so
        that distinction survives into whoever reads the log.
        """
        return tuple(symbol for symbol in self.symbols if symbol not in self.incumbent_symbols)

    def results_dir(self, symbol: str, variant: str) -> str:
        return self.version.results_template.format(symbol=symbol.lower(), variant=variant)

    def incumbent_dir(self, symbol: str) -> str | None:
        if self.incumbent_results_template is None or symbol not in self.incumbent_symbols:
            return None
        return self.incumbent_results_template.format(symbol=symbol.lower())

    def one_hour_path(self, symbol: str) -> str:
        """Resolve a symbol's one-hour cache the same way the run itself did.

        Read from the registry rather than duplicated: a second copy of these
        paths could drift from the runs themselves, which is precisely the
        failure the parity gate exists to catch.
        """
        _, one_hour, _, _, _ = symbol_run_inputs(self.version, symbol)
        return str(one_hour)


GRIDS: dict[str, GridSpec] = {
    "strategy_04_v1_2": GridSpec(
        grid_id="strategy_04_v1_2",
        version_id="strategy_04_v1_2",
        runner_module="ai_trade.backtest_strategy_04_v1_2_asset",
        verifier_module="ai_trade.verify_strategy_04_v1_2",
        sweep_module="ai_trade.sweep_strategy_04_v1_2_risk_ratio",
        summarizer_module="ai_trade.summarize_strategy_04_v1_2_ablation",
        publisher_module="ai_trade.backfill_visualization_bundles",
        incumbent_results_template="strategies/strategy_04/v1_1/results/{symbol}_1h_15m",
        incumbent_flag="--v1-1",
        # IWM, GLD and SLV are new in v1.2; v1.1 was never run on them, so they
        # have nothing to prove parity against. Listing the five that do is
        # deliberate: deriving this from the filesystem would let a wrong
        # template quietly turn the gate off for every symbol at once.
        incumbent_symbols=("SPY", "QQQ", "DIA", "EURUSD", "GBPUSD"),
    ),
}


def _run_command(spec: GridSpec, symbol: str, variant: str) -> list[str]:
    return [
        sys.executable, "-m", spec.runner_module,
        "--symbol", symbol,
        "--variant", variant,
    ]


def _verify_command(spec: GridSpec, symbol: str, variant: str, *, parity: bool) -> list[str]:
    command = [
        sys.executable, "-m", spec.verifier_module,
        "--results", spec.results_dir(symbol, variant),
        "--one-hour", spec.one_hour_path(symbol),
        "--variant", variant,
    ]
    if parity:
        incumbent = spec.incumbent_dir(symbol)
        if incumbent is not None:
            command.extend((spec.incumbent_flag, incumbent))
    return command


def plan_commands(spec: GridSpec, stages: tuple[str, ...]) -> list[list[str]]:
    """Return the exact command sequence for the requested stages, in gate order."""
    unknown = [stage for stage in stages if stage not in STAGES]
    if unknown:
        raise ValueError(f"Unknown stage(s) {unknown}; valid stages are {list(STAGES)}")

    commands: list[list[str]] = []
    if "base" in stages:
        commands.extend(_run_command(spec, symbol, spec.base_variant) for symbol in spec.symbols)
    if "parity" in stages:
        commands.extend(
            _verify_command(spec, symbol, spec.base_variant, parity=True)
            for symbol in spec.incumbent_symbols
        )
    if "variants" in stages:
        commands.extend(
            _run_command(spec, symbol, variant)
            for variant in spec.filtered_variants
            for symbol in spec.symbols
        )
    if "audit" in stages:
        commands.extend(
            _verify_command(spec, symbol, variant, parity=False)
            for variant in spec.filtered_variants
            for symbol in spec.symbols
        )
    if "sweep" in stages:
        commands.append([sys.executable, "-m", spec.sweep_module])
    if "summary" in stages:
        commands.append(
            [sys.executable, "-m", spec.summarizer_module, "--results-root", spec.results_root]
        )
    if "publish" in stages:
        # Last, so it picks up every directory the earlier stages produced.
        # Running the grid without this step leaves the dashboard showing
        # "No published audit" for runs that completed perfectly well.
        commands.append(
            [sys.executable, "-m", spec.publisher_module, "--root", spec.results_root]
        )
    return commands


def _missing_incumbents(spec: GridSpec, root: Path) -> list[str]:
    """Declared incumbent directories that do not exist on disk."""
    missing = []
    for symbol in spec.incumbent_symbols:
        incumbent = spec.incumbent_dir(symbol)
        if incumbent is not None and not (root / incumbent).is_dir():
            missing.append(f"{symbol}: {incumbent}")
    return missing


def run_grid(
    spec: GridSpec,
    stages: tuple[str, ...] = STAGES,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    """Execute the planned commands in order, stopping at the first failure.

    Because the plan is ordered base -> parity -> filtered variants, stopping
    at the first failure IS the parity gate: a failed base-parity check exits
    before any filtered variant runs.
    """
    missing = _missing_incumbents(spec, root)
    if missing:
        print(
            "STOPPED before any command: these symbols declare an incumbent that is not on disk, "
            "so their parity gate would silently not run.\n  " + "\n  ".join(missing),
            file=sys.stderr,
        )
        return 1

    if spec.symbols_without_incumbent:
        print(
            f"NOTE: {', '.join(spec.symbols_without_incumbent)} have no incumbent in "
            f"{spec.incumbent_results_template or 'this grid'} and therefore run with no parity "
            "proof. Their results show what this version does, not that the harness reproduces "
            "a known-good run."
        )

    commands = plan_commands(spec, stages)
    for number, command in enumerate(commands, start=1):
        printable = " ".join(command)
        print(f"[{number}/{len(commands)}] {printable}")
        if dry_run:
            continue
        try:
            subprocess.run(command, cwd=root, check=True)
        except subprocess.CalledProcessError as error:
            print(
                f"STOPPED at step {number}/{len(commands)} (exit {error.returncode}): {printable}\n"
                "No later stage ran. If this was the base-parity check, the harness is wrong "
                "and no other result from this grid may be read.",
                file=sys.stderr,
            )
            return error.returncode or 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a strategy version's ablation grid in gate order."
    )
    parser.add_argument("--grid", required=True, choices=tuple(sorted(GRIDS)))
    parser.add_argument(
        "--stages", nargs="+", choices=STAGES, default=list(STAGES),
        help="Subset of stages to run, for resuming a long grid. Order is always the gate order.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the command sequence only.")
    args = parser.parse_args()
    return run_grid(GRIDS[args.grid], tuple(args.stages), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
