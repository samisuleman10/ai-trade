from pathlib import Path

import pytest

from ai_trade.research_pipeline import validate_profile_data
from ai_trade.research_profiles import get_profile


def test_spy_and_gold_profiles_are_ready_for_historical_research() -> None:
    assert get_profile("strategy_01_v3_spy").is_runnable
    gold = get_profile("strategy_01_v3_mgc")
    assert gold.is_runnable
    assert gold.backtest_profile == "v3-mgc"


def test_validate_profile_data_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_profile_data(get_profile("strategy_01_v3_spy"), tmp_path)
