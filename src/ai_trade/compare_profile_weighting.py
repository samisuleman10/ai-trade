"""Measure how time-at-price weighting changes v0.3 zones and v1.1 signals.

This is the bridge report required before any volume-less instrument (spot
FX) result can be interpreted: it quantifies, on SPY/QQQ/DIA where real
volume exists, how far TPO weighting diverges from the volume weighting
that every committed equity result used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import load_ohlcv_csv
from ai_trade.strategy_04_indicator import strategy_04_v0_3_parameters
from ai_trade.strategy_04_v1_1 import Strategy04V11ExecutionParameters, candidate_signals_v1_1

DATA = {
    "SPY": ("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv", "data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"),
    "QQQ": ("data/market_data/ibkr/QQQ/v5_5y/qqq_15m.csv", "data/market_data/ibkr/QQQ/v5_5y/qqq_1h.csv"),
    "DIA": ("data/market_data/ibkr/US30_DIA/v5_5y/dia_15m.csv", "data/market_data/ibkr/US30_DIA/v5_5y/dia_1h.csv"),
}


def _qualified_zone_keys(events) -> set[tuple[str, str, float, float]]:
    """Identify qualified zones by observable geometry, not zone_id.

    Zone ids are assigned in creation order and may differ between runs
    whose zone populations diverge; timestamp, side, and boundaries are
    the stable identity of a qualification event.
    """
    return {
        (event.timestamp, event.side, event.lower, event.upper)
        for event in events
        if event.event == "qualified"
    }


def _signal_keys(signals: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {(str(signal["decision_timestamp"]), str(signal["side"])) for signal in signals}


def compare_symbol(fifteen: Iterable[OHLCVBar], hours: Iterable[OHLCVBar]) -> dict[str, object]:
    """Run the v0.3 indicator + v1.1 signals under both weightings and diff."""
    fifteen = list(fifteen)
    hours = list(hours)
    execution = Strategy04V11ExecutionParameters()
    results = {}
    for weighting in ("volume", "time"):
        params = replace(strategy_04_v0_3_parameters(), profile_weighting=weighting)
        signal_result = candidate_signals_v1_1(fifteen, hours, execution, params)
        results[weighting] = {
            "zones": _qualified_zone_keys(signal_result.indicator.events),
            "signals": _signal_keys(signal_result.signals),
        }
    volume_zones, time_zones = results["volume"]["zones"], results["time"]["zones"]
    volume_signals, time_signals = results["volume"]["signals"], results["time"]["signals"]
    return {
        "qualified_zones": {
            "volume": len(volume_zones),
            "time": len(time_zones),
            "shared": len(volume_zones & time_zones),
            "volume_only": len(volume_zones - time_zones),
            "time_only": len(time_zones - volume_zones),
        },
        "signals": {
            "volume": len(volume_signals),
            "time": len(time_signals),
            "shared": len(volume_signals & time_signals),
            "volume_only": len(volume_signals - time_signals),
            "time_only": len(time_signals - volume_signals),
        },
    }


def report_markdown(report: dict[str, object]) -> str:
    """Render the TPO-vs-volume bridge report table plus its caveats.

    The caveat paragraph exists because this report answers exactly one
    question -- how far TPO weighting diverges from volume weighting, on
    equities where both can be computed -- and nothing else. It cannot
    speak to the FX session-length / bar-scale mismatch: v0.3's bar-count
    parameters (volume_reference_max_age_bars, max_zone_age_bars,
    broken_retest_window_bars, etc.) were tuned on ~7-bars/session equity
    RTH data, while FX sessions run ~24 bars/session, roughly 3.4x tighter
    in wall-clock terms. A reader who saw only "weighting divergence is
    small" could mistake that for "the FX runs are fully validated."
    """

    lines = [
        "# TPO vs volume profile weighting - equity bridge report",
        "",
        "How far time-at-price weighting diverges from volume weighting on the",
        "symbols where both exist. Read this before interpreting any spot-FX",
        "run: FX zones are TPO-qualified, and this table is the only measured",
        "link between TPO behaviour and the volume-weighted equity results.",
        "",
        "| Symbol | Zones (vol) | Zones (time) | Shared | Signals (vol) | Signals (time) | Shared |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for symbol, result in report.items():
        zones, signals = result["qualified_zones"], result["signals"]
        lines.append(
            f"| {symbol} | {zones['volume']} | {zones['time']} | {zones['shared']} "
            f"| {signals['volume']} | {signals['time']} | {signals['shared']} |"
        )
    lines.extend(
        [
            "",
            "**Caveat:** this report measures profile-weighting divergence only, on "
            "equity data where both weightings can be computed. It cannot cover the "
            "FX session-length / bar-scale mismatch: v0.3's bar-count parameters "
            "(`volume_reference_max_age_bars`, `max_zone_age_bars`, "
            "`broken_retest_window_bars`, etc.) were tuned on ~7-bars/session equity "
            "RTH data, while FX sessions run ~24 bars/session -- roughly 3.4x tighter "
            "in wall-clock terms. A small weighting divergence here does not mean the "
            "FX runs are validated against that separate, unmeasured mismatch.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare TPO vs volume profile weighting on cached equities.")
    parser.add_argument("--symbols", nargs="+", choices=tuple(DATA), default=tuple(DATA))
    parser.add_argument("--output", type=Path, default=Path("strategies/strategy_04/analysis/tpo_vs_volume"))
    args = parser.parse_args()

    report: dict[str, object] = {}
    for symbol in args.symbols:
        fifteen_path, hours_path = DATA[symbol]
        result = compare_symbol(load_ohlcv_csv(Path(fifteen_path)), load_ohlcv_csv(Path(hours_path)))
        report[symbol] = result
        print(f"{symbol}: {json.dumps(result)}")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "REPORT.md").write_text(report_markdown(report), encoding="utf-8")
    print(f"Saved TPO bridge report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
