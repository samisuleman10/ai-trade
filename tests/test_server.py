from pathlib import Path
from ai_trade.server import load_backtest_report, parse_csv_trades


def test_parse_csv_trades():
    output_dir = Path(__file__).resolve().parent.parent / "outputs" / "strategy_01_backtest"
    fixed_trades_path = output_dir / "fixed_trades.csv"

    if fixed_trades_path.exists():
        trades = parse_csv_trades(fixed_trades_path)
        assert isinstance(trades, list)
        if len(trades) > 0:
            first_trade = trades[0]
            assert "entryPrice" in first_trade
            assert "stopPrice" in first_trade
            assert "netPnl" in first_trade
            assert first_trade["number"] == 1


def test_load_backtest_report():
    data = load_backtest_report("strategy_04", "v1_1", "SPY")
    assert "summary" in data
    assert "trades" in data
    summary = data["summary"]
    assert summary["symbol"] == "SPY"
    assert summary["startingEquity"] == 100000.0
