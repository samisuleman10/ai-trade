# AI Trade

Foundation for an AI-assisted trading application.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## IBKR portfolio sync

In TWS or IB Gateway, enable **API socket clients** and allow the local connection.
Then, with paper TWS running (default port `7497`), run:

```powershell
python -m ai_trade.sync_portfolio
```

The command is read-only: it requests account summary values and positions, then
writes a timestamped JSON file under `data/portfolio/`. For live TWS use
`--port 7496` only after confirming its API configuration.
