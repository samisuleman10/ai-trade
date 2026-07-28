"""Create a deterministic diagnostic package for Strategy 04 long trades."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from ai_trade.render_strategy_04_trade_review import render_batch


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
NEW_YORK = ZoneInfo("America/New_York")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _time(value: str) -> datetime:
    return datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _diagnostic(
    trade: dict[str, str],
    signal: dict[str, str],
    zone: dict[str, str],
    original_trade_number: int,
) -> dict[str, object]:
    entry_time = _time(trade["entry_timestamp"])
    exit_time = _time(trade["exit_timestamp"])
    local_entry = entry_time.astimezone(NEW_YORK)
    qualified_time = _time(zone["qualified_timestamp"])
    zone_lower = float(signal["zone_lower"])
    zone_upper = float(signal["zone_upper"])
    width = zone_upper - zone_lower
    hourly_atr = float(signal["one_hour_atr"])
    trigger_low = float(signal["trigger_low"])
    trigger_open = float(signal["trigger_open"])
    trigger_high = float(signal["trigger_high"])
    trigger_close = float(signal["trigger_close"])
    entry = float(trade["entry_price"])
    stop = float(trade["stop_price"])
    penetration = (zone_upper - trigger_low) / width if width > 0 else 0.0
    return {
        "original_trade_number": original_trade_number,
        "result": "win" if float(trade["net_pnl"]) > 0 else "loss",
        **trade,
        "zone_id": signal["zone_id"],
        "zone_status_at_trigger": signal["zone_status"],
        "qualified_score": int(signal["qualified_score"]),
        "current_score": int(signal["current_score"]),
        "qualified_sources": zone["qualified_sources"],
        "zone_qualified_timestamp": zone["qualified_timestamp"],
        "zone_age_hours": (entry_time - qualified_time).total_seconds() / 3600,
        "zone_lower": zone_lower,
        "zone_upper": zone_upper,
        "zone_width": width,
        "one_hour_atr": hourly_atr,
        "zone_width_atr": width / hourly_atr,
        "trigger_timestamp": signal["trigger_timestamp"],
        "trigger_open": trigger_open,
        "trigger_high": trigger_high,
        "trigger_low": trigger_low,
        "trigger_close": trigger_close,
        "trigger_body_atr": (trigger_close - trigger_open) / hourly_atr,
        "trigger_range_atr": (trigger_high - trigger_low) / hourly_atr,
        "zone_penetration_fraction": penetration,
        "trigger_below_zone_lower": trigger_low < zone_lower,
        "trigger_breached_future_stop": trigger_low <= stop,
        "entry_extension_atr": (entry - zone_upper) / hourly_atr,
        "planned_risk_atr": (entry - stop) / hourly_atr,
        "same_bar_exit": trade["entry_timestamp"] == trade["exit_timestamp"],
        "holding_hours": (exit_time - entry_time).total_seconds() / 3600,
        "entry_year": local_entry.year,
        "entry_weekday": local_entry.strftime("%A"),
        "entry_local_time": local_entry.strftime("%H:%M"),
    }


def _feature_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    numeric = (
        "zone_age_hours",
        "zone_width_atr",
        "trigger_body_atr",
        "trigger_range_atr",
        "zone_penetration_fraction",
        "entry_extension_atr",
        "planned_risk_atr",
        "holding_hours",
    )
    return {
        "trades": len(rows),
        "mean": {
            key: mean(float(row[key]) for row in rows) if rows else None
            for key in numeric
        },
        "qualified_score_counts": dict(
            sorted(Counter(str(row["qualified_score"]) for row in rows).items())
        ),
        "current_score_counts": dict(
            sorted(Counter(str(row["current_score"]) for row in rows).items())
        ),
        "zone_status_counts": dict(
            sorted(Counter(str(row["zone_status_at_trigger"]) for row in rows).items())
        ),
        "entry_hour_counts": dict(
            sorted(Counter(str(row["entry_local_time"])[:2] for row in rows).items())
        ),
        "year_counts": dict(
            sorted(Counter(str(row["entry_year"]) for row in rows).items())
        ),
        "flags": {
            "trigger_below_zone_lower": sum(
                bool(row["trigger_below_zone_lower"]) for row in rows
            ),
            "trigger_breached_future_stop": sum(
                bool(row["trigger_breached_future_stop"]) for row in rows
            ),
            "same_bar_exit": sum(bool(row["same_bar_exit"]) for row in rows),
            "entry_extension_over_0_25_atr": sum(
                float(row["entry_extension_atr"]) > 0.25 for row in rows
            ),
            "zone_older_than_120_hours": sum(
                float(row["zone_age_hours"]) > 120 for row in rows
            ),
        },
    }


def _pct(value: int, total: int) -> str:
    return f"{value} ({value / total:.1%})" if total else "0"


def _mean_value(summary: dict[str, object], key: str) -> float:
    means = summary["mean"]
    assert isinstance(means, dict)
    value = means[key]
    return float(value) if value is not None else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose and visualize every losing Strategy 04 long trade."
    )
    parser.add_argument(
        "--bars",
        type=Path,
        default=Path("data/market_data/ibkr/SPY/v4_2y/spy_15m.csv"),
    )
    parser.add_argument(
        "--trades",
        type=Path,
        default=Path("strategies/strategy_04/v1/results/spy_1h_15m/fixed_trades.csv"),
    )
    parser.add_argument(
        "--signals",
        type=Path,
        default=Path("strategies/strategy_04/v1/results/spy_1h_15m/candidate_signals.csv"),
    )
    parser.add_argument(
        "--zones",
        type=Path,
        default=Path("strategies/strategy_04/results/spy_1h_v0_3/qualified_zones.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("strategies/strategy_04/v1/results/spy_1h_15m/review/long_losses"),
    )
    args = parser.parse_args()

    trades = _read(args.trades)
    signals = _read(args.signals)
    zones = _read(args.zones)
    signal_by_key = {
        (row["decision_timestamp"], row["side"]): row
        for row in signals
    }
    zone_by_id = {row["zone_id"]: row for row in zones}

    long_diagnostics: list[dict[str, object]] = []
    loss_ledger: list[dict[str, object]] = []
    for number, trade in enumerate(trades, start=1):
        if trade["side"] != "long":
            continue
        signal = signal_by_key[(trade["decision_timestamp"], trade["side"])]
        zone = zone_by_id[signal["zone_id"]]
        diagnostic = _diagnostic(trade, signal, zone, number)
        long_diagnostics.append(diagnostic)
        if float(trade["net_pnl"]) < 0:
            loss_ledger.append({"original_trade_number": number, **trade})

    losses = [row for row in long_diagnostics if row["result"] == "loss"]
    wins = [row for row in long_diagnostics if row["result"] == "win"]
    loss_summary = _feature_summary(losses)
    win_summary = _feature_summary(wins)
    comparison = {
        "scope": "Strategy 04 v1 fixed-risk SPY long trades",
        "losses": loss_summary,
        "wins": win_summary,
        "warning": "Descriptive diagnostic only; no strategy rule was changed.",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    _write(args.output / "long_loss_trades.csv", loss_ledger)
    _write(args.output / "long_loss_diagnostics.csv", losses)
    _write(args.output / "all_long_diagnostics.csv", long_diagnostics)
    (args.output / "long_comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n",
        encoding="utf-8",
    )
    chart_manifest = render_batch(
        args.bars,
        args.signals,
        args.output / "long_loss_trades.csv",
        args.output / "charts",
        len(losses),
    )

    loss_flags = loss_summary["flags"]
    win_flags = win_summary["flags"]
    assert isinstance(loss_flags, dict) and isinstance(win_flags, dict)
    loss_count, win_count = len(losses), len(wins)
    markdown = f"""# Strategy 04 v1 — long-loss review

## Scope

- Long trades: {len(long_diagnostics)}.
- Losing longs: {loss_count}.
- Winning longs: {win_count}.
- Saved losing-long charts: {len(chart_manifest["files"])}.
- Strategy rules changed during review: **No**.

## Loss versus win diagnostics

| Feature | Losing longs | Winning longs |
| --- | ---: | ---: |
| Mean zone age | {_mean_value(loss_summary, "zone_age_hours"):.1f} hours | {_mean_value(win_summary, "zone_age_hours"):.1f} hours |
| Mean zone width | {_mean_value(loss_summary, "zone_width_atr"):.3f} ATR | {_mean_value(win_summary, "zone_width_atr"):.3f} ATR |
| Mean trigger body | {_mean_value(loss_summary, "trigger_body_atr"):.3f} ATR | {_mean_value(win_summary, "trigger_body_atr"):.3f} ATR |
| Mean trigger range | {_mean_value(loss_summary, "trigger_range_atr"):.3f} ATR | {_mean_value(win_summary, "trigger_range_atr"):.3f} ATR |
| Mean zone penetration | {_mean_value(loss_summary, "zone_penetration_fraction"):.2f}× zone width | {_mean_value(win_summary, "zone_penetration_fraction"):.2f}× zone width |
| Mean entry extension | {_mean_value(loss_summary, "entry_extension_atr"):.3f} ATR | {_mean_value(win_summary, "entry_extension_atr"):.3f} ATR |
| Mean planned risk | {_mean_value(loss_summary, "planned_risk_atr"):.3f} ATR | {_mean_value(win_summary, "planned_risk_atr"):.3f} ATR |
| Mean holding time | {_mean_value(loss_summary, "holding_hours"):.2f} hours | {_mean_value(win_summary, "holding_hours"):.2f} hours |

## Structural flags

| Flag | Losing longs | Winning longs |
| --- | ---: | ---: |
| Trigger traded below zone lower boundary | {_pct(int(loss_flags["trigger_below_zone_lower"]), loss_count)} | {_pct(int(win_flags["trigger_below_zone_lower"]), win_count)} |
| Trigger had already crossed the future stop | {_pct(int(loss_flags["trigger_breached_future_stop"]), loss_count)} | {_pct(int(win_flags["trigger_breached_future_stop"]), win_count)} |
| Entry extended more than 0.25 ATR above zone | {_pct(int(loss_flags["entry_extension_over_0_25_atr"]), loss_count)} | {_pct(int(win_flags["entry_extension_over_0_25_atr"]), win_count)} |
| Zone older than 120 hours | {_pct(int(loss_flags["zone_older_than_120_hours"]), loss_count)} | {_pct(int(win_flags["zone_older_than_120_hours"]), win_count)} |
| Stop occurred in the entry bar | {_pct(int(loss_flags["same_bar_exit"]), loss_count)} | {_pct(int(win_flags["same_bar_exit"]), win_count)} |

## Distributions

- Losing-long qualification scores: {loss_summary["qualified_score_counts"]}.
- Winning-long qualification scores: {win_summary["qualified_score_counts"]}.
- Losing-long zone states: {loss_summary["zone_status_counts"]}.
- Winning-long zone states: {win_summary["zone_status_counts"]}.
- Losing-long entry hours: {loss_summary["entry_hour_counts"]}.
- Winning-long entry hours: {win_summary["entry_hour_counts"]}.
- Losing-long years: {loss_summary["year_counts"]}.
- Winning-long years: {win_summary["year_counts"]}.

## Evidence

- [All losing-long charts](charts/index.html)
- [Losing-long diagnostics](long_loss_diagnostics.csv)
- [All-long comparison data](all_long_diagnostics.csv)
- [Machine-readable comparison](long_comparison.json)

This review is descriptive. A filter should not be added until the chart audit
confirms that a repeated feature is economically meaningful rather than fitted
to these fifteen losses.
"""
    (args.output / "LONG_LOSS_REVIEW.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    print(f"Saved {len(losses)} losing-long charts and diagnostics to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

