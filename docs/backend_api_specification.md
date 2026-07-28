# Backend API Specification & Contract for Frontend Dashboard

This document outlines the REST API contracts required by the **Frontend Strategy Dashboard** for `ai-trade`. The backend team can implement these endpoints in Python/FastAPI/Flask or any preferred service.

---

## 1. Strategy & Version Registry

### `GET /api/strategies`
Returns the full hierarchy of available strategies, version profiles, and supported backtest assets.

**Response Structure (`200 OK`):**
```json
[
  {
    "id": "strategy_04",
    "name": "Strategy 04 (Supply & Demand)",
    "description": "Supply & Demand zone indicator strategy with RRMS tier progression.",
    "defaultVersion": "v1_1",
    "versions": [
      {
        "id": "v1",
        "name": "Version 1.0 (Baseline)",
        "assets": ["SPY", "QQQ"]
      },
      {
        "id": "v1_1",
        "name": "Version 1.1 (RRMS Filtered)",
        "assets": ["SPY", "QQQ", "DIA", "MGC"]
      },
      {
        "id": "v2",
        "name": "Version 2.0 (Planned)",
        "assets": ["SPY"]
      },
      {
        "id": "v3",
        "name": "Version 3.0 (Planned)",
        "assets": ["SPY"]
      }
    ]
  },
  {
    "id": "strategy_01",
    "name": "Strategy 01 (Bill Williams Alligator)",
    "description": "Alligator + Heikin Ashi trend strategy with 4H macro confirmation.",
    "defaultVersion": "v3",
    "versions": [
      {
        "id": "v3",
        "name": "Version 3.0 (4H / 1H Entry)",
        "assets": ["SPY", "MGC", "QQQ", "DIA"]
      },
      {
        "id": "v4",
        "name": "Version 4.0 (Multi-Timeframe Cache)",
        "assets": ["SPY"]
      }
    ]
  },
  {
    "id": "strategy_02",
    "name": "Strategy 02 (Intraday Momentum)",
    "description": "Intraday EMA & ATR momentum breakout strategy.",
    "defaultVersion": "v1_5",
    "versions": [
      {
        "id": "v1_5",
        "name": "Version 1.5",
        "assets": ["SPY", "QQQ"]
      }
    ]
  },
  {
    "id": "strategy_03",
    "name": "Strategy 03 (Volatility Reset)",
    "description": "Intraday ATR volatility reset & 5-loss RRMS reset strategy.",
    "defaultVersion": "v1",
    "versions": [
      {
        "id": "v1",
        "name": "Version 1.0 (4H Weekly Reset)",
        "assets": ["SPY"]
      }
    ]
  }
]
```

---

## 2. Strategy Rules & Specification Document

### `GET /api/strategy/spec?strategy={strategyId}&version={versionId}`
Returns the raw markdown content or structured JSON for the strategy's rules (`strategy.md`).

**Response Structure (`200 OK`):**
```json
{
  "strategyId": "strategy_04",
  "versionId": "v1_1",
  "title": "Strategy 04 v1.1 Specification",
  "markdownContent": "# Strategy 04 v1.1 Rules\n\n## 1. Overview\nSupply and demand zone strategy...\n\n## 2. Entry Rules\n...",
  "riskPolicy": "Fixed 0.15% per trade with RRMS reset on 5 consecutive losses."
}
```

---

## 3. Asset Backtesting Results & Trade Logs

### `GET /api/strategy/backtest?strategy={strategyId}&version={versionId}&asset={assetId}`
Returns summary KPI metrics and individual trade records for a specific asset backtest.

**Response Structure (`200 OK`):**
```json
{
  "strategyId": "strategy_04",
  "versionId": "v1_1",
  "asset": "SPY",
  "summary": {
    "startingEquity": 100000.0,
    "endingEquityFixed": 99482.39,
    "endingEquityRrms": 100619.01,
    "totalTrades": 20,
    "wins": 8,
    "losses": 12,
    "winRate": 0.40,
    "netPnlFixed": -517.61,
    "netPnlRrms": 619.01,
    "profitFactorFixed": 0.658,
    "profitFactorRrms": 1.233,
    "maxDrawdownFixed": 556.65,
    "maxDrawdownRrms": 1218.54,
    "avgR": -0.175
  },
  "trades": [
    {
      "id": "trade-1",
      "number": 1,
      "decisionTimestamp": "2026-04-23T15:45:00Z",
      "entryTimestamp": "2026-04-23T15:45:00Z",
      "exitTimestamp": "2026-04-23T17:00:00Z",
      "side": "long",
      "rrmsTier": 0,
      "quantity": 70,
      "entryPrice": 711.66,
      "stopPrice": 709.54,
      "targetPrice": 713.78,
      "exitPrice": 709.47,
      "exitReason": "stop",
      "grossPnl": -153.35,
      "costs": 0.70,
      "netPnl": -154.05,
      "resultR": -1.038,
      "equityAfter": 99845.95
    }
  ]
}
```

---

## 4. Market Data Candles & Indicators

### `GET /api/strategy/candles?asset={assetId}&timeframe={timeframe}`
Returns candlestick bars + calculated strategy indicators (Alligator Jaw/Teeth/Lips, Supply/Demand zones).

**Response Structure (`200 OK`):**
```json
{
  "asset": "SPY",
  "timeframe": "1h",
  "bars": [
    {
      "time": 1721223000,
      "open": 550.25,
      "high": 552.10,
      "low": 549.80,
      "close": 551.90,
      "volume": 124500,
      "jaw": 548.50,
      "teeth": 549.80,
      "lips": 551.20,
      "haOpen": 550.10,
      "haClose": 551.50
    }
  ]
}
```

---

## 5. Stored Visual Graph Renders

### `GET /api/strategy/visuals?strategy={strategyId}&version={versionId}`
Returns URLs or content for stored SVG trade reviews, zone reviews, and loss diagnostic visuals.

**Response Structure (`200 OK`):**
```json
{
  "strategyId": "strategy_04",
  "versionId": "v1_1",
  "visuals": [
    {
      "id": "trade_review_batch",
      "title": "Trade Review Batch (Trades #1-#20)",
      "type": "svg",
      "url": "/api/static/visuals/strategy_04_v1_1_trades.svg"
    },
    {
      "id": "zone_review",
      "title": "Supply & Demand Zone Formation Review",
      "type": "svg",
      "url": "/api/static/visuals/strategy_04_v1_1_zones.svg"
    },
    {
      "id": "long_losses",
      "title": "Long Losses Diagnostic Breakdown",
      "type": "svg",
      "url": "/api/static/visuals/strategy_04_v1_1_long_losses.svg"
    }
  ]
}
```

---

## 6. Shadow Trading Gateway Status

### `GET /api/shadow`
Returns current shadow trading positions and NY-session decision logs.

**Response Structure (`200 OK`):**
```json
{
  "status": "active",
  "currentSession": "Regular Trading Hours (NY)",
  "nyWindowOpen": true,
  "activeIntent": {
    "symbol": "SPY",
    "side": "long",
    "entryPrice": 757.40,
    "stopPrice": 753.60,
    "targetPrice": 761.20,
    "entryTime": "2026-07-28T14:30:00Z",
    "unrealizedPnl": 185.40
  },
  "recentDecisions": [
    {
      "timestamp": "2026-07-28T14:30:00Z",
      "decision": "signal_accepted",
      "reason": "4H bullish macro filter aligned + 1H Alligator lip expansion confirmed."
    }
  ]
}
```
