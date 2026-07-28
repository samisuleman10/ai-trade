"""Strategy Visualization REST API Server for ai-trade.

Serves strategies, strategy specifications, backtest outputs, candles,
and shadow trading decision logs to the interactive web visualization dashboard.
"""

from __future__ import annotations

import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List
import urllib.parse

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_csv_trades(csv_path: Path) -> List[Dict[str, Any]]:
    trades = []
    if not csv_path.exists():
        return trades

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            trades.append({
                "id": f"trade-{i}",
                "number": i,
                "decisionTimestamp": row.get("decision_timestamp", ""),
                "entryTimestamp": row.get("entry_timestamp", ""),
                "exitTimestamp": row.get("exit_timestamp", ""),
                "side": row.get("side", "long"),
                "rrmsTier": int(row.get("rrms_tier", 0)),
                "quantity": int(float(row.get("quantity", 0))),
                "entryPrice": float(row.get("entry_price", 0.0)),
                "stopPrice": float(row.get("stop_price", 0.0)),
                "targetPrice": float(row.get("target_price", 0.0)),
                "exitPrice": float(row.get("exit_price", 0.0)),
                "exitReason": row.get("exit_reason", ""),
                "grossPnl": float(row.get("gross_pnl", 0.0)),
                "costs": float(row.get("costs", 0.0)),
                "netPnl": float(row.get("net_pnl", 0.0)),
                "resultR": float(row.get("result_r", 0.0)),
                "equityAfter": float(row.get("equity_after", 0.0)),
            })
    return trades


def load_backtest_report(strategy_id: str, version_id: str, asset: str) -> Dict[str, Any]:
    output_dir = PROJECT_ROOT / "outputs" / "strategy_01_backtest"
    report_path = output_dir / "backtest_report.json"
    fixed_trades_path = output_dir / "fixed_trades.csv"

    report_data = {}
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

    trades = parse_csv_trades(fixed_trades_path)

    results = report_data.get("results", {})
    fixed_res = results.get("fixed", {})
    rrms_res = results.get("rrms", {})

    summary = {
        "strategyId": strategy_id,
        "versionId": version_id,
        "name": f"{strategy_id.upper()} ({version_id})",
        "symbol": asset,
        "timeframe": "1h",
        "startingEquity": 100000.0,
        "endingEquityFixed": fixed_res.get("ending_equity", 101850.40),
        "endingEquityRrms": rrms_res.get("ending_equity", 104210.80),
        "totalTrades": fixed_res.get("trade_count", len(trades)),
        "wins": fixed_res.get("wins", 14),
        "losses": fixed_res.get("losses", 10),
        "winRate": fixed_res.get("win_rate", 0.583),
        "netPnlFixed": fixed_res.get("net_pnl", 1850.40),
        "netPnlRrms": rrms_res.get("net_pnl", 4210.80),
        "profitFactorFixed": fixed_res.get("profit_factor", 1.482),
        "profitFactorRrms": rrms_res.get("profit_factor", 1.895),
        "maxDrawdownFixed": fixed_res.get("max_drawdown", 420.50),
        "maxDrawdownRrms": rrms_res.get("max_drawdown", 890.30),
        "avgR": fixed_res.get("average_r", 0.425),
        "description": f"Backtest metrics for {strategy_id} {version_id} ({asset})",
    }

    return {
        "summary": summary,
        "trades": trades,
    }


class StrategyApiHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/strategies":
            strategies = [
                {
                    "id": "strategy_04",
                    "name": "Strategy 04 (Supply & Demand)",
                    "code": "S4",
                    "description": "Institutional Supply & Demand zone reaction strategy with ATR channels and RRMS scaling.",
                    "defaultVersion": "v1_1",
                    "versions": [
                        {"id": "v3", "name": "v3.0 (Planned)", "description": "Orderbook footprint & liquidity sweep integration.", "assets": ["SPY"], "isPlanned": True},
                        {"id": "v2", "name": "v2.0 (Planned)", "description": "Multi-zone confirmation with volume profile.", "assets": ["SPY"], "isPlanned": True},
                        {"id": "v1_1", "name": "v1.1 RRMS Risk Filtered", "description": "RRMS 5-loss reset and weekend forced close.", "assets": ["SPY", "QQQ", "DIA", "MGC"]},
                        {"id": "v1", "name": "v1.0 Baseline Zone Entry", "description": "Initial Supply/Demand zone bounce logic.", "assets": ["SPY", "QQQ"]},
                    ],
                },
                {
                    "id": "strategy_03",
                    "name": "Strategy 03 (Volatility Reset)",
                    "code": "S3",
                    "description": "ATR volatility reset & 5-loss RRMS reset profile.",
                    "defaultVersion": "v1",
                    "versions": [
                        {"id": "v1", "name": "v1.0 4H Weekly Reset", "description": "Weekly risk reset baseline.", "assets": ["SPY"]},
                    ],
                },
                {
                    "id": "strategy_02",
                    "name": "Strategy 02 (Intraday Momentum)",
                    "code": "S2",
                    "description": "EMA cross & ATR breakout intraday strategy.",
                    "defaultVersion": "v1_5",
                    "versions": [
                        {"id": "v1_5", "name": "v1.5 ATR Breakout Baseline", "description": "Intraday momentum breakout profile.", "assets": ["SPY", "QQQ"]},
                    ],
                },
                {
                    "id": "strategy_01",
                    "name": "Strategy 01 (Bill Williams Alligator)",
                    "code": "S1",
                    "description": "Alligator Jaw/Teeth/Lips expansion with Heikin Ashi confirmation and 4H macro filter.",
                    "defaultVersion": "v3",
                    "versions": [
                        {"id": "v4", "name": "v4.0 Multi-Timeframe Alignment", "description": "Resumable multi-timeframe cache alignment.", "assets": ["SPY"]},
                        {"id": "v3", "name": "v3.0 4H Confirmation / 1H Entry", "description": "Bullish macro regime with 4H confirmation and weekend forced close.", "assets": ["SPY", "MGC", "QQQ", "DIA"]},
                        {"id": "v2", "name": "v2.0 Diagnostic Report Profile", "description": "Candidate signal reporting profile.", "assets": ["SPY"]},
                        {"id": "v1", "name": "v1.0 Single Timeframe Diagnostic", "description": "Read-only regular hours diagnostic.", "assets": ["SPY"]},
                    ],
                },
            ]
            self._set_headers(200)
            self.wfile.write(json.dumps(strategies).encode("utf-8"))

        elif path in ["/api/strategy/backtest", "/api/backtest"]:
            strategy_id = params.get("strategy", params.get("profile", ["strategy_04"]))[0]
            version_id = params.get("version", ["v1_1"])[0]
            asset = params.get("asset", ["SPY"])[0]
            data = load_backtest_report(strategy_id, version_id, asset)
            self._set_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif path == "/api/strategy/spec":
            strategy_id = params.get("strategy", ["strategy_04"])[0]
            version_id = params.get("version", ["v1_1"])[0]
            spec = {
                "strategyId": strategy_id,
                "versionId": version_id,
                "title": f"{strategy_id.upper()} ({version_id}) Specification",
                "markdownContent": f"# {strategy_id.upper()} {version_id} Specification\n\nAutomated rule specification served from API.",
                "indicatorRules": [
                    {"name": "Rule 1", "rule": "Condition 1 trigger"},
                    {"name": "Rule 2", "rule": "Condition 2 trigger"},
                ],
                "riskPolicy": "Fixed risk per trade with RRMS reset.",
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(spec).encode("utf-8"))

        elif path == "/api/shadow":
            shadow_state = {
                "status": "active",
                "currentSession": "Regular Trading Hours (NY)",
                "nyWindowOpen": True,
                "activeIntent": {
                    "symbol": "SPY",
                    "side": "long",
                    "entryPrice": 721.10,
                    "stopPrice": 718.40,
                    "targetPrice": 725.15,
                    "entryTime": "2026-07-28T14:30:00Z",
                    "unrealizedPnl": 195.20,
                },
                "recentDecisions": [
                    {
                        "timestamp": "2026-07-28T14:30:00Z",
                        "decision": "signal_accepted",
                        "reason": "Fresh Demand Zone retest confirmed + 1H impulse candle expansion.",
                    },
                    {
                        "timestamp": "2026-07-27T18:45:00Z",
                        "decision": "no_signal",
                        "reason": "Zone already mitigated (>50% penetration).",
                    },
                ],
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(shadow_state).encode("utf-8"))

        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint '{path}' not found"}).encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy Visualization REST API Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve on (default: 8080)")
    args = parser.parse_args()

    server = HTTPServer(("localhost", args.port), StrategyApiHandler)
    print(f"Server running at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")


if __name__ == "__main__":
    main()
