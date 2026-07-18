from ai_trade.market_data import OHLCVBar
from ai_trade.download_v4_history import merge_bars


def test_merge_bars_deduplicates_timestamp_and_keeps_sorted_rows() -> None:
    old = OHLCVBar("2026-01-01T14:30:00Z", 1, 2, 0.5, 1.5, 10)
    replacement = OHLCVBar("2026-01-01T14:30:00Z", 1, 3, 0.5, 2, 12)
    newer = OHLCVBar("2026-01-01T14:35:00Z", 2, 3, 1.5, 2.5, 10)
    merged = merge_bars([old], [replacement, newer])
    assert [bar.timestamp for bar in merged] == [old.timestamp, newer.timestamp]
    assert merged[0].close == 2
