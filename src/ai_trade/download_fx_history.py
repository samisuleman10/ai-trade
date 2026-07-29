"""Resumable, read-only spot-FX midpoint history caches (EURUSD, GBPUSD).

Spot FX on IDEALPRO serves MIDPOINT bars only: there is no trade volume.
IBKR reports the sentinel ``volume = -1`` on midpoint bars; this downloader
stores an explicit ``0.0`` and records ``"volume": "none (midpoint data)"``
in the validation report so no downstream reader can mistake the column for
real volume. Unlike continuous futures, ``CASH`` requests accept an end
time, so a chunked multi-year backfill is possible.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ai_trade.download_v4_history import merge_bars
from ai_trade.market_data import (
    HistoricalDataError,
    OHLCVBar,
    fetch_historical_bars,
    fx_contract,
    save_bars,
)
from ai_trade.strategy_01 import load_ohlcv_csv

CHUNKS = {"15m": ("90 D", "15 mins"), "1h": ("1 Y", "1 hour")}
PAIRS = {"EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD")}


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalize_midpoint_volume(bars: list[OHLCVBar]) -> list[OHLCVBar]:
    """Replace IBKR's midpoint volume sentinel (-1) with an explicit zero."""
    return [replace(bar, volume=0.0) for bar in bars]


def backfill_pair_timeframe(
    *,
    pair: str,
    timeframe: str,
    directory: Path,
    target_start: datetime,
    port: int,
    client_id: int,
    pause_seconds: float,
) -> int:
    base, quote = PAIRS[pair]
    duration, bar_size = CHUNKS[timeframe]
    csv_path = directory / f"{pair.lower()}_{timeframe}.csv"
    cached = load_ohlcv_csv(csv_path) if csv_path.exists() else []
    before = len(cached)
    request_number = 0
    while not cached or _time(cached[0].timestamp) > target_start:
        # IBKR's UTC request form uses a dash between date and time and does
        # not append a timezone token.
        end = "" if not cached else _time(cached[0].timestamp).strftime("%Y%m%d-%H:%M:%S")
        incoming = normalize_midpoint_volume(
            fetch_historical_bars(
                contract=fx_contract(base, quote), duration=duration, bar_size=bar_size,
                port=port, client_id=client_id + request_number, use_rth=False,
                timeout=90, end_date_time=end, what_to_show="MIDPOINT",
            )
        )
        merged = merge_bars(cached, incoming)
        if cached and merged[0].timestamp >= cached[0].timestamp:
            raise HistoricalDataError(
                f"{pair} {timeframe} backfill made no progress at {cached[0].timestamp}."
            )
        cached = merged
        save_bars(
            cached, directory=directory, symbol=pair, timeframe=timeframe,
            source="ibkr_midpoint_research_only",
            extra={"volume": "none (midpoint data)"},
        )
        request_number += 1
        print(f"{pair} {timeframe}: {len(cached)} cached bars; earliest {cached[0].timestamp}")
        if _time(cached[0].timestamp) <= target_start:
            break
        time.sleep(pause_seconds)
    return len(cached) - before


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill local spot-FX midpoint caches with read-only IBKR bars."
    )
    parser.add_argument("--pairs", nargs="+", choices=tuple(PAIRS), default=tuple(PAIRS))
    parser.add_argument("--timeframes", nargs="+", choices=tuple(CHUNKS), default=tuple(CHUNKS))
    parser.add_argument("--target-start", default="2021-07-29", help="UTC calendar date to reach, YYYY-MM-DD.")
    parser.add_argument("--output-root", type=Path, default=Path("data/market_data/ibkr"))
    parser.add_argument("--port", type=int, default=4001)
    parser.add_argument("--client-id", type=int, default=700)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    args = parser.parse_args()
    target = datetime.strptime(args.target_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        for pair_offset, pair in enumerate(args.pairs):
            directory = args.output_root / pair / "v1_5y"
            for tf_offset, timeframe in enumerate(args.timeframes):
                added = backfill_pair_timeframe(
                    pair=pair, timeframe=timeframe, directory=directory, target_start=target,
                    port=args.port, client_id=args.client_id + pair_offset * 60 + tf_offset * 30,
                    pause_seconds=args.pause_seconds,
                )
                print(f"{pair} {timeframe}: added {added} bars; cache retained locally at {directory}")
    except HistoricalDataError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
