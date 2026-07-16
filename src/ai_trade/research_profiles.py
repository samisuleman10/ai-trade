"""Declarative research profiles for repeatable strategy experiments.

Profiles describe the experiment. They do not contain credentials or grant any
execution authority. A profile may be marked unavailable until its market-
specific sizing and session logic has been implemented and tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ResearchProfile:
    profile_id: str
    strategy_id: str
    strategy_version: str
    market: str
    symbol: str
    status: str
    backtest_profile: str
    data_directory: str
    strategy_document: str
    entry_filename: str
    trend_filename: str
    entry_timeframe: str
    trend_timeframe: str
    downloader_module: str | None = None
    download_timeframes: tuple[str, ...] = ()
    one_hour_duration: str | None = None
    four_hour_duration: str | None = None
    unavailable_reason: str | None = None

    @property
    def is_runnable(self) -> bool:
        return self.status == "ready_for_historical_research"


PROFILES: Mapping[str, ResearchProfile] = {
    "strategy_01_v3_spy": ResearchProfile(
        profile_id="strategy_01_v3_spy",
        strategy_id="strategy_01",
        strategy_version="v3",
        market="SPY",
        symbol="SPY",
        status="ready_for_historical_research",
        backtest_profile="v3",
        data_directory="data/market_data/ibkr/SPY/v3_2y",
        strategy_document="strategies/strategy_01/v3/spy/strategy.md",
        entry_filename="spy_1h.csv",
        trend_filename="spy_4h.csv",
        entry_timeframe="1h",
        trend_timeframe="4h",
        downloader_module="ai_trade.download_spy_history",
        download_timeframes=("1h", "4h"),
        one_hour_duration="2 Y",
        four_hour_duration="2 Y",
    ),
    "strategy_01_v3_mgc": ResearchProfile(
        profile_id="strategy_01_v3_mgc",
        strategy_id="strategy_01",
        strategy_version="v3",
        market="Gold / MGC",
        symbol="MGC",
        status="ready_for_historical_research",
        backtest_profile="v3-mgc",
        data_directory="data/market_data/ibkr/MGC/v3_2y",
        strategy_document="strategies/strategy_01/v3/gold/README.md",
        entry_filename="mgc_1h.csv",
        trend_filename="mgc_4h.csv",
        entry_timeframe="1h",
        trend_timeframe="4h",
        downloader_module="ai_trade.download_mgc_history",
        download_timeframes=("1h", "4h"),
        one_hour_duration="2 Y",
        four_hour_duration="2 Y",
    ),
}


def get_profile(profile_id: str) -> ResearchProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as error:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown research profile '{profile_id}'. Available: {available}") from error
