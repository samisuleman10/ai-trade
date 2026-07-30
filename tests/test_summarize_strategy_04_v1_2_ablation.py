import json
import sys
from pathlib import Path

import pytest

from ai_trade.summarize_strategy_04_v1_2_ablation import (
    SYMBOLS,
    VARIANTS,
    build_grid,
    main,
    render_markdown,
)


def _report(candidates, trade_count, win_rate, average_r, net_pnl, max_risk_zone_ratio=2.5):
    return {
        "candidate_signal_count": candidates,
        "execution_parameters": {"max_risk_zone_ratio": max_risk_zone_ratio},
        "results": {
            "fixed": {
                "trade_count": trade_count,
                "win_rate": win_rate,
                "average_r": average_r,
                "net_pnl": net_pnl,
            }
        },
    }


def _write_reports(results_root: Path, overrides=None) -> None:
    overrides = overrides or {}
    for symbol in SYMBOLS:
        for variant in VARIANTS:
            report = _report(100, 40, 0.55, 0.12, 500.0)
            report = overrides.get((symbol, variant), report)
            directory = results_root / f"{symbol.lower()}_1h_15m_{variant}"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "backtest_report.json").write_text(
                json.dumps(report), encoding="utf-8"
            )


def test_build_grid_includes_max_risk_zone_ratio_per_symbol(tmp_path):
    _write_reports(tmp_path)
    grid = build_grid(tmp_path)
    for symbol in SYMBOLS:
        assert grid[symbol]["max_risk_zone_ratio"] == 2.5
        assert set(grid[symbol]["variants"]) == set(VARIANTS)


def test_build_grid_raises_on_mixed_threshold_within_symbol(tmp_path):
    overrides = {("SPY", "a"): _report(100, 40, 0.55, 0.12, 500.0, max_risk_zone_ratio=3.0)}
    _write_reports(tmp_path, overrides)
    with pytest.raises(ValueError, match="SPY"):
        build_grid(tmp_path)


def test_render_markdown_states_threshold_and_fx_caveat(tmp_path):
    _write_reports(tmp_path)
    grid = build_grid(tmp_path)
    markdown = render_markdown(grid)
    assert "max_risk_zone_ratio" in markdown
    assert "2.5" in markdown
    assert "in-sample" in markdown
    assert "EURUSD" in markdown and "GBPUSD" in markdown
    assert "not comparable 1:1" in markdown or "not directly comparable" in markdown


def test_render_markdown_handles_zero_trade_variant_without_crashing(tmp_path):
    overrides = {
        ("QQQ", "ab"): _report(10, 0, None, None, 0.0),
    }
    _write_reports(tmp_path, overrides)
    grid = build_grid(tmp_path)
    markdown = render_markdown(grid)
    assert "n/a" in markdown


def test_main_regenerates_files_with_unchanged_numbers(tmp_path, monkeypatch):
    _write_reports(tmp_path)
    monkeypatch.setattr(sys, "argv", ["summarize_strategy_04_v1_2_ablation", "--results-root", str(tmp_path)])
    assert main() == 0
    ablation = json.loads((tmp_path / "ablation.json").read_text(encoding="utf-8"))
    for symbol in SYMBOLS:
        assert ablation[symbol]["max_risk_zone_ratio"] == 2.5
        assert ablation[symbol]["variants"]["base"]["net_pnl"] == 500.0
    md = (tmp_path / "ABLATION.md").read_text(encoding="utf-8")
    assert "max_risk_zone_ratio" in md
