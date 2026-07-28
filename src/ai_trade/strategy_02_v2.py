"""Strategy 02 v2: v1.5 plus a causal completed 15-minute VIX filter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from ai_trade.market_data import OHLCVBar
from ai_trade.strategy_01 import Strategy01Parameters
from ai_trade.strategy_02_v1_5 import Strategy02V15Parameters, candidate_signals as v15_candidate_signals


@dataclass(frozen=True)
class Strategy02V2Parameters(Strategy02V15Parameters):
    vix_threshold: float = 20.0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.vix_threshold <= 0:
            raise ValueError("vix_threshold must be positive")


def _parsed(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def candidate_signals(
    fifteen_minute_bars: Iterable[OHLCVBar],
    one_hour_bars: Iterable[OHLCVBar],
    vix_fifteen_minute_bars: Iterable[OHLCVBar],
    params: Strategy02V2Parameters = Strategy02V2Parameters(),
    alligator_params: Strategy01Parameters = Strategy01Parameters(),
) -> list[dict[str, object]]:
    """Return v1.5 candidates only when the latest completed VIX close < 20."""
    vix = list(vix_fifteen_minute_bars)
    completed_vix = [(_parsed(bar.timestamp) + timedelta(minutes=15), bar.close) for bar in vix]
    output: list[dict[str, object]] = []
    for signal in v15_candidate_signals(fifteen_minute_bars, one_hour_bars, params, alligator_params):
        decision = _parsed(str(signal["decision_timestamp"]))
        available = [item for item in completed_vix if item[0] <= decision]
        if not available:
            continue
        vix_timestamp, vix_close = available[-1]
        if vix_close >= params.vix_threshold:
            continue
        enriched = dict(signal)
        enriched.update({
            "vix_close": vix_close,
            "vix_timestamp": vix_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vix_threshold": params.vix_threshold,
        })
        output.append(enriched)
    return output
