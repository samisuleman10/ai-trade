import pytest

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_04_indicator import (
    Strategy04IndicatorParameters,
    _session_profile,
)


def _bar(low: float, high: float, volume: float) -> OHLCVBar:
    return OHLCVBar("2026-01-05T14:30:00Z", low, high, low, high, volume)


def _rows(volume_low: float, volume_high: float) -> list[OHLCVBar]:
    # One bar occupies bin 0 (100.0-101.0); two bars occupy bin 9 (109.0-110.0).
    return [
        _bar(100.0, 100.9, volume_low),
        _bar(109.0, 110.0, volume_high),
        _bar(109.0, 110.0, volume_high),
    ]


def test_volume_weighting_follows_volume():
    poc, _, _ = _session_profile(_rows(volume_low=5.0, volume_high=1.0), 10, 0.7)
    assert poc == pytest.approx(100.5)


def test_time_weighting_follows_bar_count():
    poc, _, _ = _session_profile(_rows(volume_low=5.0, volume_high=1.0), 10, 0.7, weighting="time")
    assert poc == pytest.approx(109.5)


def test_zero_volume_breaks_volume_mode_but_not_time_mode():
    rows = _rows(volume_low=0.0, volume_high=0.0)
    broken_poc, _, _ = _session_profile(rows, 10, 0.7)
    assert broken_poc == pytest.approx(100.5)  # flat profile: first bin wins (the bug)
    tpo_poc, _, _ = _session_profile(rows, 10, 0.7, weighting="time")
    assert tpo_poc == pytest.approx(109.5)  # time mode: most-occupied bin wins


def test_profile_weighting_parameter_validation():
    assert Strategy04IndicatorParameters().profile_weighting == "volume"
    Strategy04IndicatorParameters(profile_weighting="time")  # allowed
    with pytest.raises(ValueError):
        Strategy04IndicatorParameters(profile_weighting="tpo")
