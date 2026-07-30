from datetime import datetime, timedelta, timezone

from ai_trade.compare_profile_weighting import compare_symbol, report_markdown
from ai_trade.market_data import OHLCVBar


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uniform_bars(count: int, minutes: int) -> list[OHLCVBar]:
    start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    return [
        OHLCVBar(_stamp(start + timedelta(minutes=minutes * i)),
                 100 + (i % 5) * 0.2, 100.6 + (i % 5) * 0.2,
                 99.8 + (i % 5) * 0.2, 100.3 + (i % 5) * 0.2, 1_000.0)
        for i in range(count)
    ]


def test_uniform_volume_gives_identical_results():
    # When every bar carries identical volume, volume weighting and time
    # weighting distribute identically, so zones and signals must match.
    hours = _uniform_bars(200, 60)
    fifteen = _uniform_bars(800, 15)
    result = compare_symbol(fifteen, hours)
    assert result["qualified_zones"]["volume"] == result["qualified_zones"]["time"]
    assert result["qualified_zones"]["shared"] == result["qualified_zones"]["volume"]
    assert result["signals"]["volume_only"] == 0
    assert result["signals"]["time_only"] == 0


def test_report_shape():
    hours = _uniform_bars(200, 60)
    fifteen = _uniform_bars(800, 15)
    result = compare_symbol(fifteen, hours)
    for key in ("qualified_zones", "signals"):
        assert key in result
    assert set(result["qualified_zones"]) >= {"volume", "time", "shared"}
    assert set(result["signals"]) >= {"volume", "time", "shared", "volume_only", "time_only"}


def test_report_markdown_caveats_session_length_and_bar_scale():
    """This bridge report only measures TPO-vs-volume weighting divergence on
    equities; it says nothing about the FX session-length / bar-scale
    mismatch (v0.3's bar-count parameters were tuned on ~7-bars/session
    equity RTH data, and FX sessions run ~24 bars/session). Without this
    caveat, a reader could mistake "weighting divergence is small" for
    "the FX runs are fully validated."
    """

    markdown = report_markdown({"SPY": {"qualified_zones": {"volume": 10, "time": 9, "shared": 8},
                                          "signals": {"volume": 4, "time": 4, "shared": 4}}})
    lowered = markdown.lower()
    assert "session-length" in lowered or "session length" in lowered
    assert "bar-scale" in lowered or "bar scale" in lowered
