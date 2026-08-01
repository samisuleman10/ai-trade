import sys

import pytest

from ai_trade.ablation_grid import GRIDS, STAGES, plan_commands, run_grid


def _joined(commands):
    return [" ".join(command) for command in commands]


def test_grid_registry_shape():
    spec = GRIDS["strategy_04_v1_2"]
    assert spec.variants == ("base", "a", "b", "ab")
    assert spec.symbols == ("SPY", "QQQ", "DIA", "IWM", "GLD", "SLV", "EURUSD", "GBPUSD")
    assert spec.incumbent_results_template is not None


def test_incumbent_symbols_are_a_subset_of_the_grids_symbols():
    """A parity claim about a symbol the grid never runs would be meaningless."""
    for spec in GRIDS.values():
        assert set(spec.incumbent_symbols) <= set(spec.symbols)


def test_symbols_without_an_incumbent_are_named_explicitly():
    """IWM/GLD/SLV are new in v1.2 -- there is no v1.1 run for them to reproduce."""
    spec = GRIDS["strategy_04_v1_2"]
    assert spec.symbols_without_incumbent == ("IWM", "GLD", "SLV")
    assert spec.incumbent_dir("SPY") == "strategies/strategy_04/v1_1/results/spy_1h_15m"
    assert spec.incumbent_dir("IWM") is None


def test_plan_orders_base_and_parity_before_filtered_variants():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    first_filtered = next(i for i, line in enumerate(text) if "--variant a" in line)
    last_base_run = max(
        i for i, line in enumerate(text)
        if "backtest_strategy_04_v1_2_asset" in line and "--variant base" in line
    )
    last_parity = max(i for i, line in enumerate(text) if "--v1-1" in line)
    assert last_base_run < first_filtered, "base runs must precede filtered variants"
    assert last_parity < first_filtered, "parity gate must precede filtered variants"


def test_plan_covers_every_symbol_and_variant_once():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    runs = [line for line in text if "backtest_strategy_04_v1_2_asset" in line]
    assert len(runs) == 32
    for symbol in spec.symbols:
        for variant in spec.variants:
            assert sum(
                1 for line in runs if f"--symbol {symbol} " in line + " " and f"--variant {variant} " in line + " "
            ) == 1, f"{symbol}/{variant}"


def test_parity_is_planned_only_for_symbols_that_have_an_incumbent():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, ("parity",)))
    assert len(text) == len(spec.incumbent_symbols) == 5
    assert all("--v1-1" in line for line in text)
    for symbol in spec.symbols_without_incumbent:
        assert not any(f"--symbol {symbol} " in line + " " for line in text)
        assert not any(f"/{symbol.lower()}_1h_15m" in line for line in text)


def test_plan_passes_each_symbols_own_one_hour_cache_to_the_verifier():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    verifications = [line for line in text if "verify_strategy_04_v1_2" in line]
    # 5 parity checks (incumbent symbols only) + 3 filtered variants x 8 symbols.
    assert len(verifications) == 29
    eurusd = [line for line in verifications if "eurusd" in line]
    assert eurusd and all("EURUSD" in line for line in eurusd)
    gld = [line for line in verifications if "gld" in line]
    assert gld and all("GLD" in line for line in gld)
    assert all("--one-hour" in line for line in verifications)


def test_publish_runs_last_and_points_at_the_grids_results_root():
    """The audit bundles are what the dashboard reads; publishing is the final stage."""
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, STAGES))
    publishes = [line for line in text if "backfill_visualization_bundles" in line]
    assert len(publishes) == 1
    assert publishes[0] == text[-1], "publish must run after every result exists"
    assert f"--root {spec.results_root}" in publishes[0]


def test_stage_selection_limits_the_plan():
    spec = GRIDS["strategy_04_v1_2"]
    text = _joined(plan_commands(spec, ("sweep",)))
    assert len(text) == 1
    assert "sweep_strategy_04_v1_2_risk_ratio" in text[0]


def test_dry_run_executes_nothing(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        "ai_trade.ablation_grid.subprocess.run",
        lambda *args, **kwargs: calls.append(args),
    )
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES, dry_run=True) == 0
    assert calls == []
    assert "backtest_strategy_04_v1_2_asset" in capsys.readouterr().out


def test_run_announces_which_symbols_get_no_parity_proof(capsys):
    """Skipping the gate silently is the failure this warning exists to prevent."""
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES, dry_run=True) == 0
    out = capsys.readouterr().out
    assert "no incumbent" in out.lower()
    for symbol in GRIDS["strategy_04_v1_2"].symbols_without_incumbent:
        assert symbol in out


def test_a_declared_incumbent_that_is_missing_stops_the_run_before_anything_executes(monkeypatch, tmp_path):
    """A bogus incumbent path would otherwise disable the gate while looking green."""
    executed = []
    monkeypatch.setattr(
        "ai_trade.ablation_grid.subprocess.run",
        lambda command, **kwargs: executed.append(" ".join(command)),
    )
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES, root=tmp_path) != 0
    assert executed == []


def test_parity_failure_stops_before_filtered_variants(monkeypatch):
    executed = []

    def fake_run(command, **kwargs):
        executed.append(" ".join(command))
        if "--v1-1" in command:
            raise __import__("subprocess").CalledProcessError(1, command)
        return None

    monkeypatch.setattr("ai_trade.ablation_grid.subprocess.run", fake_run)
    exit_code = run_grid(GRIDS["strategy_04_v1_2"], STAGES)
    assert exit_code != 0
    assert not any("--variant a" in line for line in executed), "gate leaked into filtered variants"
    assert not any("sweep_strategy_04_v1_2" in line for line in executed)
    assert not any("backfill_visualization_bundles" in line for line in executed)


def test_successful_run_executes_every_stage(monkeypatch):
    executed = []
    monkeypatch.setattr(
        "ai_trade.ablation_grid.subprocess.run",
        lambda command, **kwargs: executed.append(" ".join(command)),
    )
    assert run_grid(GRIDS["strategy_04_v1_2"], STAGES) == 0
    assert sum(1 for line in executed if "backtest_strategy_04_v1_2_asset" in line) == 32
    assert any("sweep_strategy_04_v1_2_risk_ratio" in line for line in executed)
    assert any("summarize_strategy_04_v1_2_ablation" in line for line in executed)
    assert any("backfill_visualization_bundles" in line for line in executed)


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        plan_commands(GRIDS["strategy_04_v1_2"], ("nonsense",))
