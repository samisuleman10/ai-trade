"""Reusable detailed statistics for saved historical trade ledgers."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _group(rows: list[dict[str, str]]) -> dict[str, object]:
    wins = [row for row in rows if float(row["net_pnl"]) > 0]
    losses = [row for row in rows if float(row["net_pnl"]) < 0]
    return {
        "trades": len(rows), "wins": len(wins), "losses": len(losses),
        "breakeven": len(rows) - len(wins) - len(losses),
        "win_rate": len(wins) / len(rows) if rows else None,
        "net_pnl": sum(float(row["net_pnl"]) for row in rows),
        "average_r": mean(float(row["result_r"]) for row in rows) if rows else None,
    }


def ledger_statistics(path: Path) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    overall = _group(rows)
    by_side = {side: _group([row for row in rows if row["side"] == side]) for side in ("long", "short")}
    exit_reasons = sorted({row["exit_reason"] for row in rows})
    by_exit = {reason: _group([row for row in rows if row["exit_reason"] == reason]) for reason in exit_reasons}

    maximum_loss_streak = current_loss_streak = 0
    for row in rows:
        if float(row["net_pnl"]) < 0:
            current_loss_streak += 1
            maximum_loss_streak = max(maximum_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0
    holding_hours = [(_time(row["exit_timestamp"]) - _time(row["entry_timestamp"])).total_seconds() / 3600 for row in rows]
    return {
        **overall,
        "long": by_side["long"], "short": by_side["short"], "exit_reasons": by_exit,
        "weekend_close": by_exit.get("weekend_close", _group([])),
        "stop": by_exit.get("stop", _group([])), "target": by_exit.get("target", _group([])),
        "maximum_consecutive_losses": maximum_loss_streak,
        "average_holding_hours": mean(holding_hours) if holding_hours else None,
        "total_costs": sum(float(row["costs"]) for row in rows),
        "maximum_rrms_tier": max((int(row["rrms_tier"]) for row in rows), default=0),
    }
