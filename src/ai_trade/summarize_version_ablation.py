"""Generic cross-variant ablation table for any registered strategy version.

Reads every committed backtest report (each supported symbol x each variant)
and writes one comparison table so filter effects can be attributed per
symbol. The symbol list, the variant list, the swept parameter's name and the
run-directory layout all come from the ``VersionSpec`` -- a hand-maintained
copy of any of them is how IWM, GLD and SLV came to be backtested but
silently absent from the v1.2 summary table. Interpretation stays with the
human: promotion requires out-of-sample confirmation and sensitivity
evidence this table alone cannot provide.

Every symbol's variants must agree on the swept parameter's value; a
mismatch means a partial re-run mixed thresholds and is reported as an error
rather than silently summarized.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from ai_trade.strategy_registry import VERSIONS, VersionSpec


def strategy_title(spec: VersionSpec) -> str:
    """Heading form of the strategy id ("strategy_04" -> "Strategy 04")."""
    return spec.strategy_id.replace("_", " ").title()


def baseline_variant(spec: VersionSpec) -> str:
    """The empty-override variant every delta is measured against.

    The registry documents "the ablation base is the empty override", so the
    name is derived rather than assumed to be "base" -- the deltas below and
    the sweep's rejection counts both anchor on it.
    """
    for name, overrides in spec.variants.items():
        if not overrides:
            return name
    raise ValueError(f"{spec.version_id} declares no empty-override baseline variant")


def _format_metric(value: object, format_spec: str) -> str:
    # A zero-trade variant records null metrics; "n/a" keeps the row visible
    # instead of crashing the whole table on one empty cell.
    return "n/a" if value is None else format(value, format_spec)


def _run_directory(spec: VersionSpec, results_root: Path, symbol: str, variant: str) -> Path:
    # Only the template's basename is used: the caller picks the root, so the
    # table can be built against a scratch copy of the results in tests.
    name = Path(spec.results_template.format(symbol=symbol.lower(), variant=variant)).name
    return results_root / name


def build_grid(spec: VersionSpec, results_root: Path) -> dict[str, dict[str, object]]:
    """Load every symbol's reports into {symbol: {<sweep_parameter>, variants}}."""
    grid: dict[str, dict[str, object]] = {}
    for symbol in spec.supported_symbols:
        variants: dict[str, dict[str, object]] = {}
        thresholds: dict[str, float] = {}
        for variant in spec.variants:
            report_path = (
                _run_directory(spec, results_root, symbol, variant) / "backtest_report.json"
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            fixed = report["results"]["fixed"]
            thresholds[variant] = report["execution_parameters"][spec.sweep_parameter]
            variants[variant] = {
                "candidates": report["candidate_signal_count"],
                "trades": fixed["trade_count"],
                "win_rate": fixed["win_rate"],
                "average_r": fixed["average_r"],
                "net_pnl": fixed["net_pnl"],
            }
        distinct = set(thresholds.values())
        if len(distinct) != 1:
            raise ValueError(
                f"{symbol}: {spec.sweep_parameter} differs across variants "
                f"(guards against a mixed-threshold partial re-run): {thresholds}"
            )
        grid[symbol] = {
            spec.sweep_parameter: distinct.pop(),
            "variants": variants,
        }
    return grid


def render_markdown(spec: VersionSpec, grid: dict[str, dict[str, object]]) -> str:
    parameter = spec.sweep_parameter
    thresholds = {symbol: data[parameter] for symbol, data in grid.items()}
    distinct_thresholds = set(thresholds.values())
    # "Filter A rows" names the mechanism the threshold gates. The wording is
    # required by the v1.2 spec and kept verbatim; only the parameter name is
    # substituted. A version whose mechanisms are named differently needs a
    # prose field in the registry, not an edit here.
    if len(distinct_thresholds) == 1:
        threshold_value = distinct_thresholds.pop()
        threshold_sentence = (
            f"Filter A rows use {parameter} = {threshold_value:g}, an "
            "in-sample, unvalidated threshold -- see the sweep."
        )
    else:
        per_symbol = ", ".join(f"{symbol}={value:g}" for symbol, value in thresholds.items())
        threshold_sentence = (
            f"Filter A rows use {parameter} per symbol ({per_symbol}), an "
            "in-sample, unvalidated threshold -- see the sweep."
        )
    lines = [
        f"# {strategy_title(spec)} {spec.version_label} ablation -- fixed 0.15% risk",
        "",
        # Spec-required caveats, verbatim: every number is in-sample and the
        # table attributes effects without approving anything.
        "Every number is in-sample. Per the spec, a filter that helps one",
        "symbol must not be adopted for others without its own evidence, and",
        "promotion additionally requires out-of-sample confirmation, parameter",
        "sensitivity, and cost stress. This table attributes effects; it does",
        "not approve anything.",
        "",
        threshold_sentence,
        "",
    ]
    if spec.fx_data:
        # The FX non-comparability caveat is required wording too; the pair
        # list is the spec's, and a version with no FX runs omits the sentence
        # rather than warn about rows that do not exist.
        lines += [
            f"FX rows ({'/'.join(spec.fx_data)}) are TPO-zone, midpoint-data, modelled-spread "
            "runs with equity-tuned bar-count windows and are not comparable 1:1 "
            "with equity rows.",
            "",
        ]
    base_name = baseline_variant(spec)
    for symbol, data in grid.items():
        variants = data["variants"]
        base = variants[base_name]
        lines += [
            f"## {symbol}",
            "",
            "| Variant | Candidates | Trades | Win rate | Avg R | Net P&L | dNet vs base |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for variant, row in variants.items():
            delta = row["net_pnl"] - base["net_pnl"]
            win_rate_str = _format_metric(row["win_rate"], ".3f")
            average_r_str = _format_metric(row["average_r"], "+.4f")
            lines.append(
                f"| {variant} | {row['candidates']} | {row['trades']} "
                f"| {win_rate_str} | {average_r_str} "
                f"| {row['net_pnl']:+.2f} | {delta:+.2f} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_summary(spec: VersionSpec, results_root: Path) -> int:
    """Build the grid and write ablation.json + ABLATION.md beside the runs."""
    grid = build_grid(spec, results_root)
    (results_root / "ablation.json").write_text(
        json.dumps(grid, indent=2) + "\n", encoding="utf-8"
    )
    (results_root / "ABLATION.md").write_text(render_markdown(spec, grid), encoding="utf-8")
    print(f"Saved ablation summary to {results_root}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a registered strategy version's ablation grid."
    )
    parser.add_argument("--version", required=True, choices=tuple(VERSIONS))
    parser.add_argument("--results-root", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = VERSIONS[args.version]
    results_root = args.results_root
    if results_root is None:
        # The per-run directories land under the template's parent, so the
        # summary lands beside them by default.
        results_root = Path(spec.results_template).parent
    return write_summary(spec, results_root)


if __name__ == "__main__":
    raise SystemExit(main())
