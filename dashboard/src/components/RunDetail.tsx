import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { fetchDataset } from '../catalog';
import type { CatalogEntry } from '../catalog';
import type { ExitReason, Trade, TradeSide } from '../types';
import { conditionsFor, familyInfo } from '../strategyDescriptions';
import { EquityChart } from './EquityChart';
import { TradeTable } from './TradeTable';

interface RunDetailProps {
  entry: CatalogEntry;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Visualization-contract shapes (snake_case, as returned by the API). These
// intentionally mirror only the fields RunDetail and its children need --
// see docs/design/strategy_visualization/shared/architecture_and_data_contract.md
// for the full contract.
// ---------------------------------------------------------------------------

interface ContractTrade {
  trade_id: string;
  status: string;
  decision_timestamp: string;
  entry_timestamp: string;
  exit_timestamp: string;
  side: string;
  rrms_tier: number;
  quantity: number;
  entry_price: number;
  stop_price: number;
  target_price: number;
  exit_price: number;
  exit_reason: string;
  gross_pnl: number;
  costs: number;
  net_pnl: number;
  result_r: number;
  equity_after: number;
}

interface TradesDataset {
  dataset_id: string;
  kind: string;
  trades: ContractTrade[];
}

interface PerformancePoint {
  timestamp: string;
  equity: number;
  drawdown?: number;
  drawdown_percent?: number;
  peak_equity?: number;
  trade_id?: string | null;
}

interface PerformanceSummary {
  average_r?: number;
  ending_equity?: number;
  exit_reasons?: Record<string, number>;
  long_trades?: number;
  losses?: number;
  max_drawdown?: number;
  net_pnl?: number;
  profit_factor?: number;
  short_trades?: number;
  trade_count?: number;
  win_rate?: number;
  wins?: number;
}

interface PerformanceDataset {
  dataset_id: string;
  kind: string;
  points: PerformancePoint[];
  summary?: PerformanceSummary;
}

type Variant = 'fixed' | 'rrms';
type FetchStatus = 'loading' | 'loaded' | 'error';

const em = '—';

const money = (value: unknown): string =>
  typeof value === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
        signDisplay: 'always',
      }).format(value)
    : em;

const plainMoney = (value: unknown): string =>
  typeof value === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }).format(value)
    : em;

const drawdownMoney = (value: unknown): string =>
  typeof value === 'number'
    ? `-${new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }).format(Math.abs(value))}`
    : em;

const percent = (value: unknown): string => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : em);

const ratio = (value: unknown): string => (typeof value === 'number' ? value.toFixed(2) : em);

const rMultiple = (value: unknown): string =>
  typeof value === 'number' ? `${value >= 0 ? '+' : ''}${value.toFixed(3)}R` : em;

const count = (value: unknown): string => (typeof value === 'number' ? String(value) : em);

/**
 * Maps a visualization-contract trade (snake_case) onto the camelCase
 * `Trade` shape that TradeTable consumes. `number` has no
 * contract equivalent, so callers pass the 1-based ledger position.
 */
function mapContractTrade(trade: ContractTrade, number: number): Trade {
  return {
    id: trade.trade_id,
    number,
    decisionTimestamp: trade.decision_timestamp,
    entryTimestamp: trade.entry_timestamp,
    exitTimestamp: trade.exit_timestamp,
    side: trade.side as TradeSide,
    rrmsTier: trade.rrms_tier,
    quantity: trade.quantity,
    entryPrice: trade.entry_price,
    stopPrice: trade.stop_price,
    targetPrice: trade.target_price,
    exitPrice: trade.exit_price,
    exitReason: trade.exit_reason as ExitReason,
    grossPnl: trade.gross_pnl,
    costs: trade.costs,
    netPnl: trade.net_pnl,
    resultR: trade.result_r,
    equityAfter: trade.equity_after,
  };
}

export function RunDetail({ entry, onClose }: RunDetailProps) {
  const hasRrms =
    entry.dataset_ids.includes('trades_rrms') && entry.dataset_ids.includes('performance_rrms');

  const [variant, setVariant] = useState<Variant>('fixed');
  const [status, setStatus] = useState<FetchStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tradesDataset, setTradesDataset] = useState<TradesDataset | null>(null);
  const [performanceDataset, setPerformanceDataset] = useState<PerformanceDataset | null>(null);

  // Reset to the fixed variant whenever the selected run changes so a
  // toggle choice from a previous run never leaks into the next one.
  useEffect(() => {
    setVariant('fixed');
  }, [entry.bundle_id]);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    setErrorMessage(null);

    Promise.all([
      fetchDataset<TradesDataset>(entry.bundle_id, `trades_${variant}`),
      fetchDataset<PerformanceDataset>(entry.bundle_id, `performance_${variant}`),
    ])
      .then(([trades, performance]) => {
        if (cancelled) return;
        if (!Array.isArray(performance.points) || performance.points.length === 0) {
          setStatus('error');
          setErrorMessage('Performance dataset has no equity points to anchor the chart.');
          return;
        }
        setTradesDataset(trades);
        setPerformanceDataset(performance);
        setStatus('loaded');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus('error');
        setErrorMessage(err instanceof Error ? err.message : 'Failed to load run data.');
      });

    return () => {
      cancelled = true;
    };
  }, [entry.bundle_id, variant]);

  const trades = useMemo<Trade[]>(() => {
    if (!tradesDataset) return [];
    return tradesDataset.trades.map((trade, index) => mapContractTrade(trade, index + 1));
  }, [tradesDataset]);

  // The equity chart is fed the producer's recorded points directly. Building a
  // synthetic StrategySummary here previously required substituting 0 for every
  // absent field, which fabricated numbers on the way into the chart.
  const equityPoints = performanceDataset?.points ?? [];
  const variantLabel = variant === 'rrms' ? 'RRMS' : 'Fixed 0.15%';

  const summary = performanceDataset?.summary;

  return (
    <div className="space-y-5">
      <section className="s4-panel flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="s4-icon-button"
            aria-label="Back to all runs"
            onClick={onClose}
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <div className="s4-eyebrow">
              {entry.run.strategy_id} / {entry.run.strategy_version}
            </div>
            <h2 className="mt-1 text-base font-semibold text-slate-950">
              {entry.instrument.symbol || em}
              <span className="ml-2 text-xs font-normal text-slate-500">{entry.run.run_id}</span>
            </h2>
            <p className="mt-1 max-w-3xl text-xs text-slate-500">
              {conditionsFor(entry.run.strategy_id) ?? familyInfo(entry.run.strategy_id).summary}
            </p>
          </div>
        </div>

        {hasRrms && (
          <div className="s4-segment">
            <button
              type="button"
              aria-pressed={variant === 'fixed'}
              className={variant === 'fixed' ? 'is-active' : ''}
              onClick={() => setVariant('fixed')}
            >
              Fixed
            </button>
            <button
              type="button"
              aria-pressed={variant === 'rrms'}
              className={variant === 'rrms' ? 'is-active' : ''}
              onClick={() => setVariant('rrms')}
            >
              RRMS
            </button>
          </div>
        )}
      </section>

      {status === 'loading' && (
        <section className="s4-panel p-8 text-center">
          <p className="text-sm text-slate-600">
            Loading trade ledger and equity curve for {entry.instrument.symbol || entry.bundle_id}…
          </p>
        </section>
      )}

      {status === 'error' && (
        <section className="s4-panel p-8 text-center">
          <div className="text-sm font-semibold text-slate-900">Could not load this run</div>
          <p className="mt-2 text-xs text-slate-500">{errorMessage ?? 'Unknown error.'}</p>
        </section>
      )}

      {status === 'loaded' && equityPoints.length > 0 && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            {[
              ['Trades', count(summary?.trade_count)],
              ['Net P&L', money(summary?.net_pnl)],
              ['Win rate', percent(summary?.win_rate)],
              ['Profit factor', ratio(summary?.profit_factor)],
              ['Max drawdown', drawdownMoney(summary?.max_drawdown)],
              ['Avg result / trade', rMultiple(summary?.average_r)],
              ['Ending equity', plainMoney(summary?.ending_equity)],
            ].map(([label, value]) => (
              <article key={label} className="s4-stat-card">
                <div className="s4-eyebrow">{label}</div>
                <div className="mt-1 font-mono text-lg font-semibold text-slate-950">{value}</div>
              </article>
            ))}
          </section>

          <EquityChart points={equityPoints} variantLabel={variantLabel} />

          <TradeTable trades={trades} onFocusTrade={() => {}} />
        </>
      )}
    </div>
  );
}
