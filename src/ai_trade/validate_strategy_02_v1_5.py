"""Reproducible validation package for locked Strategy 02 v1.5."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from ai_trade.backtest_strategy_01 import BacktestConfig, _entry_allowed, run_backtest, summarize, write_results
from ai_trade.render_strategy_02_trade_review import _panel
from ai_trade.strategy_01 import Strategy01Parameters, load_ohlcv_csv
from ai_trade.strategy_02_v1_5 import Strategy02V15Parameters, candidate_signals


ROOT = Path(__file__).resolve().parents[2]
FIFTEEN_PATH = ROOT / "data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"
HOURLY_PATH = ROOT / "data/market_data/ibkr/SPY/v4_2y/spy_1h.csv"
DEFAULT_OUTPUT = ROOT / "strategies/strategy_02/v1_5/results/validation"
SPLIT_TIMESTAMP = "2025-07-17T13:30:00Z"


def _config(**updates) -> BacktestConfig:
    base = BacktestConfig(
        allowed_direction="both",
        block_opening_hour_entries=True,
        block_final_hour_entries=True,
        block_friday_entries=True,
        entry_interval_minutes=15,
        force_friday_close=True,
    )
    return replace(base, **updates)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def freeze_manifest(output: Path) -> dict[str, object]:
    files = [
        ROOT / "strategies/strategy_02/v1_5/strategy.md",
        ROOT / "src/ai_trade/strategy_02_v1_5.py",
        ROOT / "src/ai_trade/strategy_02_v1_3.py",
        ROOT / "src/ai_trade/strategy_02_v1_1.py",
        ROOT / "src/ai_trade/strategy_02_v1.py",
        ROOT / "src/ai_trade/strategy_01.py",
        ROOT / "src/ai_trade/backtest_strategy_01.py",
        ROOT / "src/ai_trade/backtest_strategy_02.py",
        FIFTEEN_PATH,
        HOURLY_PATH,
    ]
    manifest = {
        "strategy_id": "strategy_02_v1_5_multi_timeframe_alligator_zigzag",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "status": "locked_for_validation",
        "strategy_parameters": asdict(Strategy02V15Parameters()),
        "alligator_parameters": asdict(Strategy01Parameters()),
        "backtest_configuration": asdict(_config()),
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in files
        ],
    }
    (output / "freeze_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def out_of_sample(fifteen, hourly, output: Path) -> dict[str, object]:
    train_fifteen = [bar for bar in fifteen if bar.timestamp < SPLIT_TIMESTAMP]
    train_hourly = [bar for bar in hourly if bar.timestamp < SPLIT_TIMESTAMP]
    train_signals = candidate_signals(train_fifteen, train_hourly)
    all_signals = candidate_signals(fifteen, hourly)
    test_signals = [signal for signal in all_signals if str(signal["entry_timestamp"]) >= SPLIT_TIMESTAMP]
    config = _config()
    report: dict[str, object] = {
        "method": "strict chronological holdout",
        "split_timestamp": SPLIT_TIMESTAMP,
        "training_range": [train_fifteen[0].timestamp, train_fifteen[-1].timestamp],
        "out_of_sample_range": [SPLIT_TIMESTAMP, fifteen[-1].timestamp],
        "training_bar_count": len(train_fifteen),
        "out_of_sample_bar_count": sum(bar.timestamp >= SPLIT_TIMESTAMP for bar in fifteen),
        "training_candidate_count": len(train_signals),
        "out_of_sample_candidate_count": len(test_signals),
        "results": {},
    }
    for mode in ("fixed", "rrms"):
        training_trades = run_backtest(train_fifteen, train_signals, mode, config)
        test_trades = run_backtest(fifteen, test_signals, mode, config)
        report["results"][mode] = {
            "training": summarize(training_trades, config.starting_equity),
            "out_of_sample": summarize(test_trades, config.starting_equity),
        }
        write_results(test_trades, summarize(test_trades, config.starting_equity), mode, output / "out_of_sample")
    (output / "out_of_sample_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def sensitivity(fifteen, hourly, output: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    config = _config()
    for depth in (14, 18, 22):
        for deviation in (3, 5, 7):
            for backstep in (2, 3, 4):
                params = replace(
                    Strategy02V15Parameters(),
                    zigzag_depth=depth,
                    zigzag_deviation=deviation,
                    zigzag_backstep=backstep,
                )
                signals = candidate_signals(fifteen, hourly, params=params)
                trades = run_backtest(fifteen, signals, "fixed", config)
                summary = summarize(trades, config.starting_equity)
                rows.append(
                    {
                        "zigzag_depth": depth,
                        "zigzag_deviation": deviation,
                        "zigzag_backstep": backstep,
                        "candidate_count": len(signals),
                        **summary,
                    }
                )
    _write_csv(output / "parameter_sensitivity.csv", rows)
    return rows


def cost_stress(fifteen, hourly, output: Path) -> list[dict[str, object]]:
    signals = candidate_signals(fifteen, hourly)
    rows: list[dict[str, object]] = []
    for slippage in (0.0, 1.0, 2.0, 5.0):
        for commission in (0.0, 0.005, 0.01, 0.02):
            config = _config(slippage_bps_per_side=slippage, commission_per_share_per_side=commission)
            trades = run_backtest(fifteen, signals, "fixed", config)
            rows.append(
                {
                    "slippage_bps_per_side": slippage,
                    "commission_per_share_per_side": commission,
                    **summarize(trades, config.starting_equity),
                }
            )
    _write_csv(output / "cost_slippage_stress.csv", rows)
    return rows


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def monte_carlo(trades, output: Path, simulations: int = 10_000) -> dict[str, object]:
    observed_r = [trade.result_r for trade in trades]
    rng = random.Random(20260723)
    ending_equities: list[float] = []
    drawdowns: list[float] = []
    losing_streaks: list[int] = []
    for _ in range(simulations):
        equity = peak = 100_000.0
        maximum_drawdown = 0.0
        current_losing_streak = maximum_losing_streak = 0
        for result_r in (rng.choice(observed_r) for _ in observed_r):
            equity += equity * 0.0015 * result_r
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, peak - equity)
            if result_r < 0:
                current_losing_streak += 1
                maximum_losing_streak = max(maximum_losing_streak, current_losing_streak)
            else:
                current_losing_streak = 0
        ending_equities.append(equity)
        drawdowns.append(maximum_drawdown)
        losing_streaks.append(maximum_losing_streak)
    report = {
        "method": "seeded bootstrap of observed fixed-risk trade R outcomes",
        "seed": 20260723,
        "simulations": simulations,
        "trades_per_simulation": len(observed_r),
        "ending_equity": {
            "p05": _percentile(ending_equities, 0.05),
            "median": _percentile(ending_equities, 0.50),
            "p95": _percentile(ending_equities, 0.95),
            "probability_below_start": sum(value < 100_000 for value in ending_equities) / simulations,
        },
        "maximum_drawdown": {
            "median": _percentile(drawdowns, 0.50),
            "p95": _percentile(drawdowns, 0.95),
            "p99": _percentile(drawdowns, 0.99),
        },
        "maximum_losing_streak": {
            "median": _percentile([float(value) for value in losing_streaks], 0.50),
            "p95": _percentile([float(value) for value in losing_streaks], 0.95),
        },
        "limitation": "Bootstrap reuses the small observed sample and does not model regime shifts or serial dependence.",
    }
    (output / "monte_carlo.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def trade_audit(fifteen, hourly, trades, output: Path) -> dict[str, object]:
    signals = candidate_signals(fifteen, hourly)
    by_entry = {str(signal["entry_timestamp"]): signal for signal in signals}
    by_bar = {bar.timestamp: bar for bar in fifteen}
    rows: list[dict[str, object]] = []
    for number, trade in enumerate(trades, 1):
        signal = by_entry.get(trade.entry_timestamp)
        entry_bar = by_bar[trade.entry_timestamp]
        structure_confirmed = str(signal["structure_confirmed_timestamp"]) if signal else ""
        structure_pivot = str(signal["structure_pivot_timestamp"]) if signal else ""
        expected_entry = entry_bar.open * (
            1.0001 if trade.side == "long" else 0.9999
        )
        checks = {
            "signal_found": signal is not None,
            "decision_equals_entry_open": trade.decision_timestamp == trade.entry_timestamp,
            "structure_confirmed_before_decision": bool(signal) and structure_confirmed <= trade.decision_timestamp,
            "pivot_before_confirmation": bool(signal) and structure_pivot <= structure_confirmed,
            "entry_uses_next_bar_open_plus_slippage": abs(trade.entry_price - expected_entry) < 1e-8,
            "exit_not_before_entry": trade.exit_timestamp >= trade.entry_timestamp,
            "stop_geometry_valid": (
                trade.stop_price < trade.entry_price if trade.side == "long" else trade.stop_price > trade.entry_price
            ),
            "target_geometry_valid": (
                trade.target_price > trade.entry_price if trade.side == "long" else trade.target_price < trade.entry_price
            ),
        }
        rows.append(
            {
                "trade_number": number,
                "entry_timestamp": trade.entry_timestamp,
                "exit_timestamp": trade.exit_timestamp,
                "side": trade.side,
                "exit_reason": trade.exit_reason,
                "structure_pivot_timestamp": structure_pivot,
                "structure_confirmed_timestamp": structure_confirmed,
                "net_pnl": round(trade.net_pnl, 6),
                "result_r": round(trade.result_r, 6),
                **checks,
                "all_checks_pass": all(checks.values()),
            }
        )
    _write_csv(output / "trade_causality_audit.csv", rows)
    report = {
        "trade_count": len(rows),
        "trades_passing_all_automated_checks": sum(bool(row["all_checks_pass"]) for row in rows),
        "failed_trade_numbers": [row["trade_number"] for row in rows if not row["all_checks_pass"]],
        "checks": [key for key in rows[0] if key not in {
            "trade_number", "entry_timestamp", "exit_timestamp", "side", "exit_reason",
            "structure_pivot_timestamp", "structure_confirmed_timestamp", "net_pnl", "result_r", "all_checks_pass"
        }],
    }
    (output / "trade_audit_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def trade_review_svgs(fifteen, trades, output: Path) -> list[str]:
    review_dir = output / "trade_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for page, start in enumerate(range(0, len(trades), 4), 1):
        selected = trades[start:start + 4]
        panels = "".join(
            _panel(
                fifteen,
                asdict(trade) | {key: str(value) for key, value in asdict(trade).items()},
                0 if index % 2 == 0 else 600,
                0 if index < 2 else 330,
                580,
                310,
                start + index + 1,
            )
            for index, trade in enumerate(selected)
        )
        document = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640">
<style>.grid{{stroke:#555;stroke-width:.6}}.label{{fill:#eee;font:16px sans-serif}}.tick{{fill:#c4c4c4;font:11px sans-serif}}.marker{{stroke:#fff;stroke-dasharray:4 3}}.exit{{stroke:#a78bfa;stroke-dasharray:3 3}}</style>
<rect width="1200" height="640" fill="#171717"/>{panels}</svg>'''
        path = review_dir / f"trades_{start + 1:02d}_{start + len(selected):02d}.svg"
        path.write_text(document, encoding="utf-8")
        created.append(path.relative_to(ROOT).as_posix())
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate locked Strategy 02 v1.5.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fifteen = load_ohlcv_csv(FIFTEEN_PATH)
    hourly = load_ohlcv_csv(HOURLY_PATH)
    base_signals = candidate_signals(fifteen, hourly)
    base_trades = run_backtest(fifteen, base_signals, "fixed", _config())

    manifest = freeze_manifest(args.output)
    oos = out_of_sample(fifteen, hourly, args.output)
    sensitivity_rows = sensitivity(fifteen, hourly, args.output)
    cost_rows = cost_stress(fifteen, hourly, args.output)
    monte = monte_carlo(base_trades, args.output)
    audit = trade_audit(fifteen, hourly, base_trades, args.output)
    review_files = trade_review_svgs(fifteen, base_trades, args.output)
    base_row = next(
        row for row in sensitivity_rows
        if row["zigzag_depth"] == 18 and row["zigzag_deviation"] == 5 and row["zigzag_backstep"] == 3
    )
    summary = {
        "strategy_id": manifest["strategy_id"],
        "freeze_manifest": "freeze_manifest.json",
        "out_of_sample": oos,
        "base_parameter_result": base_row,
        "parameter_sensitivity": {
            "runs": len(sensitivity_rows),
            "profitable_runs": sum(float(row["net_pnl"]) > 0 for row in sensitivity_rows),
            "minimum_net_pnl": min(float(row["net_pnl"]) for row in sensitivity_rows),
            "maximum_net_pnl": max(float(row["net_pnl"]) for row in sensitivity_rows),
        },
        "cost_slippage_stress": {
            "runs": len(cost_rows),
            "profitable_runs": sum(float(row["net_pnl"]) > 0 for row in cost_rows),
            "worst_case": min(cost_rows, key=lambda row: float(row["net_pnl"])),
        },
        "monte_carlo": monte,
        "trade_audit": audit,
        "trade_review_files": review_files,
        "warning": "Historical research only; no shadow, paper, or live authorization.",
    }
    (args.output / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "trades": len(base_trades),
        "review_pages": len(review_files),
        "audit_passed": audit["trades_passing_all_automated_checks"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
