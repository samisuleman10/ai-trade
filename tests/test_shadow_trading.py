from ai_trade.shadow_trading import ShadowCycleConfig, _risk_decision
from ai_trade.shadow_runner import NEW_YORK, scheduled_decision_timestamp
from ai_trade.shadow_monitor import next_rrms_tier
from datetime import datetime
from zoneinfo import ZoneInfo


def test_risk_decision_sizes_a_long_within_rrms_budget() -> None:
    result = _risk_decision(
        {"side": "long", "entry_reference": 100.0, "jaw": 98.0},
        ShadowCycleConfig(simulated_equity=100_000.0, rrms_tier=0),
    )
    assert result["status"] == "accepted"
    assert result["quantity"] == 74
    assert result["expected_loss_with_modeled_cost"] <= result["risk_budget"]


def test_risk_decision_rejects_non_bullish_macro_stance() -> None:
    result = _risk_decision(
        {"side": "long", "entry_reference": 100.0, "jaw": 98.0},
        ShadowCycleConfig(macro_stance="neutral"),
    )
    assert result == {"status": "rejected", "reason": "macro_stance_not_bullish"}


def test_schedule_uses_new_york_time_and_excludes_friday() -> None:
    new_york = ZoneInfo("America/New_York")
    assert scheduled_decision_timestamp(datetime(2026, 7, 13, 10, 31, tzinfo=new_york)) == "2026-07-13T14:30:00Z"
    assert scheduled_decision_timestamp(datetime(2026, 7, 17, 10, 31, tzinfo=new_york)) is None


def test_rrms_tier_is_normal_without_a_closed_shadow_trade(tmp_path) -> None:
    assert next_rrms_tier(tmp_path) == 0
