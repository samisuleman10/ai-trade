"""Generic parameter sweep for any registered strategy version.

The v1.2 spec requires sweeping its threshold before the value may be
trusted, and every future version carries the same obligation for whatever
tunable its spec names. Which parameter, over what grid, and across which
symbols all come from the ``VersionSpec``; the sweep itself is version-blind
plumbing. The report is evidence for a human decision -- nothing here
selects a value.

The one fact the registry does not encode is *which variant isolates the
swept parameter's mechanism* (for v1.2: Filter A alone, Filter B off, so any
effect is attributable). Guessing it from variant names would go silently
wrong for a future version, so ``variant`` is required and each version's
wrapper pins its own.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional, Sequence

from ai_trade.backtest_strategy_01 import BacktestConfig, run_backtest, summarize
from ai_trade.market_data import OHLCVBar
from ai_trade.run_strategy_version import symbol_run_inputs
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import Strategy04IndicatorParameters
from ai_trade.strategy_registry import VERSIONS, VersionSpec
from ai_trade.summarize_version_ablation import baseline_variant, strategy_title


def sweep_symbol(
    spec: VersionSpec,
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    indicator_params: Strategy04IndicatorParameters,
    config: BacktestConfig,
    thresholds: Optional[Sequence[float]] = None,
    *,
    variant: str,
) -> list[dict[str, object]]:
    """Evaluate ``variant`` with the sweep parameter at each grid value.

    The signal builder rebuilds the one-hour indicator at every threshold.
    That is deliberate waste: the spec's builder is the version's only public
    entry point, and reusing zone events across thresholds would demand a
    second, version-specific hook for an offline report that runs once per
    grid. The builder is deterministic, so the rows are identical either way.
    """
    fifteen = list(fifteen_minute_bars)
    hours = list(one_hour_bars)
    grid = spec.sweep_grid if thresholds is None else thresholds

    # Rejection counts are measured against the empty-override baseline, the
    # same anchor the ablation table uses.
    baseline = spec.params_type(**dict(spec.variants[baseline_variant(spec)]))
    unfiltered = spec.signal_builder(fifteen, hours, baseline, indicator_params).signals

    rows: list[dict[str, object]] = []
    for threshold in grid:
        overrides = dict(spec.variants[variant])
        overrides[spec.sweep_parameter] = threshold
        params = spec.params_type(**overrides)
        signals = spec.signal_builder(fifteen, hours, params, indicator_params).signals
        trades = run_backtest(fifteen, signals, "fixed", config)
        summary = summarize(trades, config.starting_equity)
        rows.append(
            {
                "threshold": threshold,
                "candidate_signal_count": len(signals),
                "rejected_vs_unfiltered": len(unfiltered) - len(signals),
                "trade_count": summary["trade_count"],
                "win_rate": summary["win_rate"],
                "average_r": summary["average_r"],
                "net_pnl": summary["net_pnl"],
            }
        )
    return rows


def render_markdown(spec: VersionSpec, report: dict[str, object], variant: str) -> str:
    # The caveat sentences are required verbatim by the version spec ("no
    # threshold is selected", the in-sample warning). Only the parameter
    # name, the dataclass default and the version label are substituted; a
    # version whose mechanisms need different prose gets prose fields in the
    # registry, not edits here. The title's "Filter A" label falls out of the
    # variant name under this strategy family's naming convention.
    lines = [
        f"# {strategy_title(spec)} {spec.version_label} -- {spec.sweep_parameter} sweep "
        f"(Filter {variant.upper()} only)",
        "",
        "Fixed 0.15% risk. Filter B off throughout so effects are attributable.",
        "**No threshold is selected by this report.** The spec requires a human",
        "decision informed by sensitivity: a real edge should persist across",
        "neighbouring thresholds, not appear at exactly one value. All caveats",
        f"from the {spec.version_label} spec's Research warning apply, including that the "
        f"{spec.sweep_default:g}",
        "exploratory split was chosen in-sample. Signal counts need not be",
        "monotonic in the threshold: a rejected reaction leaves its zone",
        "unconsumed, which can create additional later signals.",
        "",
    ]
    held_out = [s for s in report["symbols"] if s in spec.holdout_symbols]
    if held_out:
        # The v1.3 holdout report raised exactly this hazard for FX when the
        # sweep grew to cover it. The sweep is the one artifact that can spend
        # a holdout without running a single new backtest: reading these rows
        # to pick a value fits the parameter to the instruments that were
        # supposed to test it.
        lines += [
            f"**{', '.join(held_out)} are holdout instruments** for "
            f"{spec.version_label} (their data arrived after the rules were fixed at "
            f"{spec.rules_fixed}). Selecting {spec.sweep_parameter} using their rows "
            "would spend the holdout: the parameter would then be fitted to the very "
            "instruments held back to test it. They are reported here for sensitivity "
            "only.",
            "",
        ]
    for symbol, block in report["symbols"].items():
        lines += [
            f"## {symbol}",
            "",
            "| Threshold | Signals | Rejected | Trades | Win rate | Avg R | Net P&L |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in block["rows"]:
            lines.append(
                f"| {row['threshold']} | {row['candidate_signal_count']} "
                f"| {row['rejected_vs_unfiltered']} | {row['trade_count']} "
                f"| {row['win_rate']:.3f} | {row['average_r']:+.4f} "
                f"| {row['net_pnl']:+.2f} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def run_sweep(
    spec: VersionSpec,
    symbols: Sequence[str],
    output: Path,
    *,
    variant: str,
    thresholds: Optional[Sequence[float]] = None,
    json_name: Optional[str] = None,
) -> int:
    """Sweep every requested symbol and write the JSON + Markdown evidence."""
    grid = tuple(spec.sweep_grid if thresholds is None else thresholds)
    report: dict[str, object] = {"thresholds": list(grid), "symbols": {}}
    for symbol in symbols:
        fifteen_path, hours_path, config, indicator_params, market = symbol_run_inputs(
            spec, symbol
        )
        rows = sweep_symbol(
            spec,
            load_ohlcv_csv(fifteen_path),
            load_ohlcv_csv(hours_path),
            indicator_params,
            config,
            grid,
            variant=variant,
        )
        report["symbols"][symbol] = {"market": market, "rows": rows}
        print(f"{symbol}: {json.dumps(rows[-1])}")

    output.mkdir(parents=True, exist_ok=True)
    # v1.2's wrapper pins the historical "risk_ratio_sweep.json" name that the
    # committed results and the v1.3 holdout report reference; a new version
    # gets a name derived from its own parameter.
    name = json_name if json_name is not None else f"{spec.sweep_parameter}_sweep.json"
    (output / name).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "SWEEP.md").write_text(render_markdown(spec, report, variant), encoding="utf-8")
    print(f"Saved sweep to {output}")
    return 0


def build_parser(spec: VersionSpec) -> argparse.ArgumentParser:
    """Symbols default to everything the spec supports, so the sweep covers
    whatever the grid runs."""
    parser = argparse.ArgumentParser(
        description="Sweep a registered version's spec-named parameter per symbol."
    )
    parser.add_argument("--version", required=True, choices=tuple(VERSIONS))
    parser.add_argument(
        "--symbols",
        nargs="+",
        choices=spec.supported_symbols,
        default=spec.supported_symbols,
    )
    # Which variant isolates the swept parameter is version knowledge the
    # registry does not carry; requiring it beats guessing (see module doc).
    parser.add_argument("--variant", required=True, choices=tuple(spec.variants))
    parser.add_argument(
        "--output", type=Path, default=Path(spec.results_template).parent / "sweep"
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    # Two-stage parse: --version decides the symbol and variant choices, so
    # it must be known before the real parser exists (the same pattern as
    # run_strategy_version).
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--version")
    known, _ = pre.parse_known_args(argv)
    spec = VERSIONS.get(known.version) if known.version else None
    if spec is not None:
        parser = build_parser(spec)
    else:
        parser = argparse.ArgumentParser(
            description="Sweep a registered version's spec-named parameter per symbol."
        )
        parser.add_argument("--version", required=True, choices=tuple(VERSIONS))
    args = parser.parse_args(argv)
    return run_sweep(VERSIONS[args.version], args.symbols, args.output, variant=args.variant)


if __name__ == "__main__":
    raise SystemExit(main())
