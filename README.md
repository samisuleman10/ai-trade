# AI Trade

<!-- KEEP THIS SECTION FIRST. Do not delete it or move it further down the file. -->

## Quick start: run the dashboard

Two terminals. The virtual environment and npm packages are already installed —
do **not** run `python -m venv .venv` again, and never run it while a venv is
active (Windows locks the running `python.exe` and it fails with a permission
error).

Terminal 1 — the API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ai_trade.server --port 8080
```

Terminal 2 — the dashboard:

```powershell
.\.venv\Scripts\Activate.ps1
npm run dev --prefix dashboard
```

Then open <http://localhost:5173>.

Check the API is healthy:

```powershell
curl http://127.0.0.1:8080/health
```

Expect `{"status": "ok", "valid_bundles": 48, "invalid_bundles": 0}`.

### Which tabs need the API

| Tab | Needs the API |
| --- | --- |
| Performance, Compare assets, Rules | No |
| Chart & trades (Strategy 04 trade audit) | No — the fixture is bundled |
| All runs (every run, strategies 01–04) | **Yes** |

### Adding a run

Nothing manual. A backtest publishes its own visualization bundle and the run
appears in **All runs** on refresh:

```powershell
python -m ai_trade.backtest_strategy_04_v1_1
```

To re-publish bundles for result directories created outside a backtest:

```powershell
python -m ai_trade.backfill_visualization_bundles --dry-run
```

Drop `--dry-run` to write. It only ever adds `visualization/` subdirectories;
it never modifies existing result artifacts.

### Tests

```powershell
python -m pytest -q
```

## Project direction

This project is being built as a controlled trading lifecycle: define a
strategy, validate it against stored historical data, run it in shadow/paper
mode, apply hard risk controls, execute through venue adapters, reconcile
actual fills, monitor performance, and improve or retire the strategy based on
evidence. Read the full [Trading System Blueprint](docs/TRADING_SYSTEM_BLUEPRINT.md).

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

## MEXC spot and futures sync

Add `MEXC_API_KEY` and `MEXC_API_SECRET` to the local `.env` file. Use a
restricted, IP-whitelisted key and do not enable trading or withdrawal
permissions for this sync. Then run:

```powershell
python -m ai_trade.sync_mexc
```

The command only reads spot balances, futures account assets, and open futures
positions, then writes a timestamped JSON file under `data/mexc/`.

## Strategy 01: SPY data and diagnostic

Strategy specifications live in [`strategies/`](strategies/). Strategy 01 is a
read-only Alligator + Heikin Ashi diagnostic for SPY; it does not place orders.
With TWS running and its API socket enabled, download the initial regular-hours
history from the connected live TWS port:

```powershell
python -m ai_trade.download_spy_history --port 7496
python -m ai_trade.diagnose_strategy_01
python -m ai_trade.backtest_strategy_01
```

The first command saves 15-minute and 1-hour SPY bars under
`data/market_data/` (ignored by Git). The second writes candidate-signal and
parameter reports under `outputs/strategy_01_diagnostic/`. These are diagnostics
only; they include neither a macro filter nor order submission. The backtest
then saves fixed-risk and RRMS simulated trade logs and summaries under
`outputs/strategy_01_backtest/`.

### Strategy 01 v3: 4-hour confirmation / 1-hour entry

The v3 experiment is a separate, historical-only profile: manual bullish
macro regime (long only), no first/final-hour or Friday entries, weekday
overnight holding, and forced Friday close. Download its required confirmation
data and run it without overwriting v1/v2 outputs:

```powershell
python -m ai_trade.download_spy_history --port 7496 --output data/market_data/ibkr/SPY/v3_2y --timeframes 1h 4h --one-hour-duration "2 Y" --four-hour-duration "2 Y"
python -m ai_trade.backtest_strategy_01 --profile v3 --one-hour data/market_data/ibkr/SPY/v3_2y/spy_1h.csv --four-hour data/market_data/ibkr/SPY/v3_2y/spy_4h.csv --output outputs/strategy_01/v3/spy/two_year_friday_close
```

The specification is in `strategies/strategy_01/v3/spy/strategy.md`.
This profile is not authorised for paper or live trading.

## Deterministic research pipeline

Run an entire approved historical-research profile with one command. The
pipeline validates saved market data, runs the shared backtest, creates the
trade-review chart, adds profile/data metadata to the report, and can create an
immutable archive with hashes. Existing run IDs and archive folders are never
overwritten.

```powershell
python -m ai_trade.research_pipeline --profile strategy_01_v3_spy --run-id two_year_reproducible_2026-07-16 --archive docs/strategy_01/v3/spy/pipeline_archives/two_year_reproducible_2026-07-16
```

Add `--refresh-data --port 7496` only when you deliberately want the pipeline
to make a fresh **read-only** IBKR historical-data request before the run.

Profiles live in `src/ai_trade/research_profiles.py`. The MGC profile has a
separate futures-aware historical model: a 10-ounce multiplier, whole-contract
risk sizing, a Globex session window, and a fee-recovery floor. It remains
research-only because verified broker commissions, front-month rollover, margin,
and delivery controls are still required before paper or live trading.

Run its preliminary historical test with:

```powershell
python -m ai_trade.research_pipeline --profile strategy_01_v3_mgc --run-id two_year_clean_preliminary_2026-07-16 --archive docs/strategy_01/v3/gold/pipeline_archives/two_year_clean_preliminary_2026-07-16
```

The Nasdaq-100 test uses QQQ as its liquid, tradeable proxy while keeping the
locked SPY v3 rules unchanged:

```powershell
python -m ai_trade.research_pipeline --profile strategy_01_v3_qqq --run-id two_year_preliminary_2026-07-16 --refresh-data --port 7496 --archive docs/strategy_01/v3/qqq/pipeline_archives/two_year_preliminary_2026-07-16
```

The Dow 30 test uses DIA as its ETF proxy:

```powershell
python -m ai_trade.research_pipeline --profile strategy_01_v3_dia --run-id two_year_preliminary_2026-07-16 --refresh-data --port 7496 --archive docs/strategy_01/v3/dia/pipeline_archives/two_year_preliminary_2026-07-16
```

## Strategy 01 v3 shadow trading

The next development stage is a forward **shadow-trading** loop for SPY. It
will create and monitor simulated trade intents only; it has no broker-order
authority. The rules, data records, safety gateway, and requirements before
paper trading are defined in
[`docs/strategy_01/v3/shadow_trading_specification.md`](docs/strategy_01/v3/shadow_trading_specification.md).

The first implementation is a deterministic local replay cycle. It reads saved
bars, writes an auditable signal/no-signal or trade-intent record, and has no
broker imports or order functions:

```powershell
python -m ai_trade.shadow_trading --one-hour data/market_data/ibkr/SPY/v3_2y/spy_1h.csv --four-hour data/market_data/ibkr/SPY/v3_2y/spy_4h.csv --decision-timestamp 2026-07-16T14:30:00Z
```

To begin a manual forward shadow run, leave TWS/IB Gateway open with its local
API socket on `7496`, then run `./scripts/start_shadow_runner.ps1`. It refreshes
only the required read-only SPY bars in the five allowed Monday–Thursday New
York-time windows. It does not place or transmit orders.

Accepted shadow intents are monitored against later completed 1-hour bars. The
runner writes closed results to `shadow_trades.jsonl`; only one SPY shadow
position may be open at a time. Use `--force-weekend-close` in the separate
Friday monitoring cycle to apply the documented weekend-close rule.

## Strategy 01 v4: multi-timeframe confirmation

Strategy 01 v4 is a separate, specified-but-not-yet-implemented hypothesis:
completed 1-hour, 15-minute, and 5-minute Alligator states must agree before a
15-minute entry is allowed. The versioned specification is in
[`strategies/strategy_01/v4/strategy.md`](strategies/strategy_01/v4/strategy.md).

Its multi-timeframe cache is resumable: existing bars are retained and only
missing older chunks are requested. To extend the saved SPY cache to a target
date, run:

```powershell
python -m ai_trade.download_v4_history --output data/market_data/ibkr/SPY/v4_2y --target-start 2024-07-17 --port 7496
```

## Trading-tools watchlist

Tools discovered during research are recorded separately from approved project
components in [`docs/notes/trading_tools_watchlist.md`](docs/notes/trading_tools_watchlist.md).
Listing a tool is not approval to install it, connect credentials, or trade.
