"""Local shadow-position monitoring for Strategy 01 v3; no broker orders."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ai_trade.market_data import OHLCVBar


NEW_YORK = ZoneInfo("America/New_York")
ROUND_TRIP_COST_PER_SHARE = 0.01


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_json_line(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def open_positions(output_directory: Path) -> list[dict[str, Any]]:
    """Return accepted intents not yet represented by a closed shadow trade."""
    intents = _read_json_lines(output_directory / "trade_intents.jsonl")
    closed = {record["cycle_id"] for record in _read_json_lines(output_directory / "shadow_trades.jsonl")}
    return [
        record
        for record in intents
        if record.get("outcome", {}).get("status") == "accepted" and record.get("cycle_id") not in closed
    ]


def monitor_positions(
    *,
    bars: Iterable[OHLCVBar],
    cutoff_timestamp: str,
    output_directory: Path,
    force_weekend_close: bool = False,
) -> list[dict[str, Any]]:
    """Close eligible local-only shadow positions using completed bars only.

    Bars whose start is at or after ``cutoff_timestamp`` are deliberately
    ignored, because that bar is not complete at the time of the decision.
    Stop has priority over target if both occur inside one bar.
    """
    completed = [bar for bar in bars if bar.timestamp < cutoff_timestamp]
    outcomes: list[dict[str, Any]] = []
    for intent in open_positions(output_directory):
        proposal = intent["outcome"]
        signal = proposal["signal"]
        entry_time = signal["entry_timestamp"]
        eligible = [bar for bar in completed if bar.timestamp >= entry_time]
        exit_bar: OHLCVBar | None = None
        exit_price: float | None = None
        reason: str | None = None
        for bar in eligible:
            if bar.low <= proposal["stop_price"]:
                exit_bar, exit_price, reason = bar, proposal["stop_price"], "stop"
                break
            if bar.high >= proposal["target_price"]:
                exit_bar, exit_price, reason = bar, proposal["target_price"], "target"
                break
        if exit_bar is None and force_weekend_close and eligible:
            friday_bars = [
                bar
                for bar in eligible
                if datetime.strptime(bar.timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(NEW_YORK).weekday() == 4
            ]
            if friday_bars:
                exit_bar, exit_price, reason = friday_bars[-1], friday_bars[-1].close, "weekend_close"
        if exit_bar is None or exit_price is None or reason is None:
            continue
        quantity = int(proposal["quantity"])
        entry_price = float(proposal["entry_price"])
        gross_pnl = quantity * (exit_price - entry_price)
        costs = quantity * ROUND_TRIP_COST_PER_SHARE
        net_pnl = gross_pnl - costs
        price_risk = entry_price - float(proposal["stop_price"])
        record = {
            "cycle_id": intent["cycle_id"],
            "strategy_id": intent["strategy_id"],
            "strategy_version": intent["strategy_version"],
            "instrument": "SPY",
            "entry_timestamp": entry_time,
            "exit_timestamp": exit_bar.timestamp,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "stop_price": proposal["stop_price"],
            "target_price": proposal["target_price"],
            "quantity": quantity,
            "rrms_tier": proposal["rrms_tier"],
            "exit_reason": reason,
            "gross_pnl": round(gross_pnl, 6),
            "costs": round(costs, 6),
            "net_pnl": round(net_pnl, 6),
            "result_r": round(net_pnl / (quantity * price_risk), 6),
            "execution_authority": "none",
        }
        _append_json_line(output_directory / "shadow_trades.jsonl", record)
        outcomes.append(record)
    return outcomes


def next_rrms_tier(output_directory: Path) -> int:
    """Derive the next four-step RRMS tier from the most recent closed trade."""
    trades = _read_json_lines(output_directory / "shadow_trades.jsonl")
    if not trades:
        return 0
    last = trades[-1]
    if last["net_pnl"] > 0:
        return 0
    if last["exit_reason"] == "stop":
        return (int(last["rrms_tier"]) + 1) % 4
    return int(last["rrms_tier"])
