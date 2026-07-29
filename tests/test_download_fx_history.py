import json

from ai_trade.download_fx_history import normalize_midpoint_volume
from ai_trade.market_data import OHLCVBar, save_bars


def _bar(timestamp: str, volume: float) -> OHLCVBar:
    return OHLCVBar(timestamp, 1.1, 1.2, 1.0, 1.15, volume)


def test_normalize_midpoint_volume_zeroes_ibkr_sentinel():
    bars = [_bar("2026-01-05T00:00:00Z", -1.0), _bar("2026-01-05T00:15:00Z", -1.0)]
    normalized = normalize_midpoint_volume(bars)
    assert [bar.volume for bar in normalized] == [0.0, 0.0]
    # Prices and timestamps are untouched.
    assert normalized[0].timestamp == "2026-01-05T00:00:00Z"
    assert normalized[0].close == 1.15


def test_save_bars_extra_lands_in_validation_report(tmp_path):
    bars = [_bar("2026-01-05T00:00:00Z", 0.0)]
    _, report_path = save_bars(
        bars, directory=tmp_path, symbol="EURUSD", timeframe="15m",
        source="ibkr_midpoint_research_only",
        extra={"volume": "none (midpoint data)"},
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["volume"] == "none (midpoint data)"
    assert report["source"] == "ibkr_midpoint_research_only"
    assert report["validation"]["valid"] is True


def test_backfill_uses_midpoint_and_normalizes(monkeypatch, tmp_path):
    import ai_trade.download_fx_history as dl

    calls = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return [
            OHLCVBar("2026-01-05T00:00:00Z", 1.1, 1.2, 1.0, 1.15, -1.0),
            OHLCVBar("2026-01-05T00:15:00Z", 1.15, 1.2, 1.1, 1.18, -1.0),
        ]

    monkeypatch.setattr(dl, "fetch_historical_bars", fake_fetch)
    added = dl.backfill_pair_timeframe(
        pair="EURUSD", timeframe="15m", directory=tmp_path,
        target_start=dl._time("2026-01-05T00:00:00Z"),
        port=4001, client_id=700, pause_seconds=0.0,
    )
    assert added == 2
    assert calls[0]["what_to_show"] == "MIDPOINT"
    assert calls[0]["use_rth"] is False
    assert calls[0]["contract"].secType == "CASH"
    saved = (tmp_path / "eurusd_15m.csv").read_text(encoding="utf-8")
    assert ",-1.0" not in saved  # sentinel volume never persisted
