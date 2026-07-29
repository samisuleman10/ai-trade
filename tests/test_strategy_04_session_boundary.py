import pytest

from ai_trade.strategy_04_indicator import Strategy04IndicatorParameters, _session_date


def test_calendar_boundary_uses_new_york_date():
    # 2026-07-26T21:00:00Z is Sunday 17:00 EDT.
    assert _session_date("2026-07-26T21:00:00Z", "calendar") == "2026-07-26"


def test_fx_boundary_rolls_at_17_et():
    # Sunday 17:00 EDT opens Monday's FX session.
    assert _session_date("2026-07-26T21:00:00Z", "fx_17et") == "2026-07-27"
    # Sunday 16:45 EDT is still Sunday's session.
    assert _session_date("2026-07-26T20:45:00Z", "fx_17et") == "2026-07-26"


def test_fx_boundary_respects_winter_offset():
    # 2026-01-05T22:00:00Z is Monday 17:00 EST (UTC-5): rolls to Tuesday.
    assert _session_date("2026-01-05T22:00:00Z", "fx_17et") == "2026-01-06"
    # 2026-01-05T21:45:00Z is Monday 16:45 EST: stays Monday.
    assert _session_date("2026-01-05T21:45:00Z", "fx_17et") == "2026-01-05"


def test_session_day_boundary_parameter_validation():
    assert Strategy04IndicatorParameters().session_day_boundary == "calendar"
    Strategy04IndicatorParameters(session_day_boundary="fx_17et")  # allowed
    with pytest.raises(ValueError):
        Strategy04IndicatorParameters(session_day_boundary="utc")
