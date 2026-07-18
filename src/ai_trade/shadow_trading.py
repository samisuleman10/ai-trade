"""Deterministic, local-only shadow-cycle evaluation for Strategy 01 v3.

This module intentionally has no broker client imports and no order methods.
It evaluates saved completed bars, records one simulated trade proposal, and is
safe to replay because a decision timestamp is written only once.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_trade.backtest_strategy_01 import BacktestConfig, RRMS_TIERS, _entry_allowed
from ai_trade.market_data import validate_bars
from ai_trade.strategy_01 import candidate_signals, load_ohlcv_csv


STRATEGY_ID = "strategy_01_v3_bill_williams_alligator_rrms"
COMMISSION_PER_SHARE_ROUND_TRIP = 0.01


@dataclass(frozen=True)
class ShadowCycleConfig:
    macro_stance: str = "bullish"
    simulated_equity: float = 100_000.0
    rrms_tier: int = 0


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_json_line(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def _risk_decision(signal: dict[str, object], config: ShadowCycleConfig) -> dict[str, Any]:
    """Return an accepted/rejected local-only proposed position for one signal."""
    if config.macro_stance != "bullish":
        return {"status": "rejected", "reason": "macro_stance_not_bullish"}
    if not 0 <= config.rrms_tier < len(RRMS_TIERS):
        return {"status": "rejected", "reason": "invalid_rrms_tier"}

    entry = float(signal["entry_reference"])
    stop = float(signal["jaw"])
    if str(signal["side"]) != "long":
        return {"status": "rejected", "reason": "direction_not_allowed"}
    if stop >= entry:
        return {"status": "rejected", "reason": "stop_not_below_entry"}

    price_risk = entry - stop
    risk_percent = RRMS_TIERS[config.rrms_tier]
    risk_budget = config.simulated_equity * risk_percent
    cost_per_share = COMMISSION_PER_SHARE_ROUND_TRIP
    quantity = int(risk_budget // (price_risk + cost_per_share))
    if quantity < 1:
        return {"status": "rejected", "reason": "minimum_share_risk_exceeds_budget"}

    expected_loss = quantity * (price_risk + cost_per_share)
    return {
        "status": "accepted",
        "reason": "all_risk_checks_passed",
        "rrms_tier": config.rrms_tier,
        "risk_percent": risk_percent,
        "risk_budget": round(risk_budget, 6),
        "quantity": quantity,
        "entry_price": entry,
        "stop_price": stop,
        "target_price": entry + price_risk,
        "expected_loss_with_modeled_cost": round(expected_loss, 6),
    }


def run_cycle(
    *,
    one_hour_path: Path,
    four_hour_path: Path,
    decision_timestamp: str,
    output_directory: Path,
    config: ShadowCycleConfig = ShadowCycleConfig(),
    preflight_rejection: str | None = None,
) -> dict[str, Any]:
    """Evaluate one specified v3 decision timestamp from saved local bars.

    ``decision_timestamp`` is the open of the next 1-hour bar, and therefore
    the close of the completed signal bar. Only data at or before that timestamp
    is passed into signal evaluation. The next-bar opening reference is known at
    that instant; no later OHLC values are used by the signal calculation.
    """
    entry_bars = [bar for bar in load_ohlcv_csv(one_hour_path) if bar.timestamp <= decision_timestamp]
    trend_bars = [bar for bar in load_ohlcv_csv(four_hour_path) if bar.timestamp <= decision_timestamp]
    if not entry_bars or not trend_bars:
        raise ValueError("No local bars available at the requested decision timestamp.")
    try:
        _parse_timestamp(decision_timestamp)
    except ValueError as error:
        raise ValueError("decision_timestamp must use ISO UTC format, e.g. 2026-07-16T14:30:00Z") from error
    if entry_bars[-1].timestamp != decision_timestamp:
        raise ValueError("The next 1-hour entry bar is not available yet; retry when its opening bar is present.")

    cycle_log = output_directory / "cycle_log.jsonl"
    intent_log = output_directory / "trade_intents.jsonl"
    cycle_id = f"{STRATEGY_ID}:SPY:{decision_timestamp}"
    if any(record.get("cycle_id") == cycle_id for record in _read_json_lines(cycle_log)):
        return {"cycle_id": cycle_id, "status": "duplicate", "reason": "decision_timestamp_already_recorded"}

    validation = {"one_hour": validate_bars(entry_bars), "four_hour": validate_bars(trend_bars)}
    if preflight_rejection:
        outcome: dict[str, Any] = {"status": "rejected", "reason": preflight_rejection}
    elif not all(report["valid"] for report in validation.values()):
        outcome: dict[str, Any] = {"status": "rejected", "reason": "invalid_local_market_data"}
    else:
        signals = candidate_signals(
            entry_bars,
            trend_bars,
            entry_interval_minutes=60,
            trend_interval_minutes=240,
            minimum_decision_close_time=None,
            infer_trend_close_from_session_boundaries=True,
        )
        matching = [signal for signal in signals if signal["decision_timestamp"] == decision_timestamp]
        allowed = [
            signal
            for signal in matching
            if _entry_allowed(
                str(signal["entry_timestamp"]),
                str(signal["side"]),
                BacktestConfig(
                    allowed_direction="long",
                    block_opening_hour_entries=True,
                    block_final_hour_entries=True,
                    block_friday_entries=True,
                    entry_interval_minutes=60,
                ),
            )
        ]
        if not allowed:
            outcome = {"status": "no_signal", "reason": "no_eligible_v3_long_signal"}
        else:
            proposal = allowed[0]
            outcome = {**_risk_decision(proposal, config), "signal": proposal}

    record: dict[str, Any] = {
        "cycle_id": cycle_id,
        "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strategy_id": STRATEGY_ID,
        "strategy_version": "v3",
        "instrument": "SPY",
        "decision_timestamp": decision_timestamp,
        "data_validation": validation,
        "configuration": asdict(config),
        "outcome": outcome,
        "execution_authority": "none",
    }
    _append_json_line(cycle_log, record)
    if outcome["status"] in {"accepted", "rejected"}:
        _append_json_line(intent_log, record)
    return {"cycle_id": cycle_id, **outcome}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one local-only Strategy 01 v3 shadow cycle; never submits an order.")
    parser.add_argument("--one-hour", type=Path, required=True)
    parser.add_argument("--four-hour", type=Path, required=True)
    parser.add_argument("--decision-timestamp", required=True, help="UTC, e.g. 2026-07-16T14:30:00Z")
    parser.add_argument("--output", type=Path, default=Path("outputs/shadow_trading/strategy_01/v3/spy"))
    parser.add_argument("--macro-stance", choices=("bullish", "neutral", "bearish"), default="bullish")
    parser.add_argument("--simulated-equity", type=float, default=100_000.0)
    parser.add_argument("--rrms-tier", type=int, default=0)
    args = parser.parse_args()
    result = run_cycle(
        one_hour_path=args.one_hour,
        four_hour_path=args.four_hour,
        decision_timestamp=args.decision_timestamp,
        output_directory=args.output,
        config=ShadowCycleConfig(args.macro_stance, args.simulated_equity, args.rrms_tier),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
