import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { fetchDataset } from '../catalog';
import type { CatalogEntry } from '../catalog';
import type { ExitReason, Trade, TradeSide } from '../types';
import { conditionsFor, familyInfo } from '../strategyDescriptions';
import { auditFailures, failedTradeCount, useRunAudit } from '../ledgerAudit';
import type { RunAuditStatus, TradeAuditDataset } from '../ledgerAudit';
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

/** How many failing checks to list before collapsing the rest into a count. */
const MAX_LISTED_FAILURES = 25;

/**
 * Whether this run's recorded trades survive their own arithmetic.
 *
 * Deliberately a verdict and its counter-evidence, not a second audit
 * screen: a pass needs one line, and a failure needs the check that failed
 * with the value it expected beside the value it found. The per-trade
 * deep-dive with zone geometry and bar windows stays in the Strategy 04
 * view, which is the only strategy that publishes the evidence for it.
 *
 * `absent` renders nothing at all. A bundle published before these checks
 * existed has not been audited, and an empty failure list would read as a
 * clean one.
 */
function LedgerAudit({
  status,
  dataset,
  variant,
}: {
  status: RunAuditStatus;
  dataset: TradeAuditDataset | null;
  variant: Variant;
}) {
  if (status === 'absent') return null;

  if (status === 'loading' || status === 'error') {
    return (
      <section className="s4-panel px-5 py-4">
        <div className="s4-eyebrow">Ledger audit</div>
        <p className="mt-1 text-xs text-slate-500">
          {status === 'loading'
            ? 'Checking each recorded trade against its own arithmetic…'
            : 'The audit for this run could not be loaded, so its trades are unverified here.'}
        </p>
      </section>
    );
  }

  const trades = dataset?.trades ?? [];
  const failures = dataset ? auditFailures(dataset) : [];
  const failingTrades = dataset ? failedTradeCount(dataset) : 0;
  const listed = failures.slice(0, MAX_LISTED_FAILURES);

  return (
    <section className="s4-panel overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <div className="s4-eyebrow">Ledger audit</div>
          <h3 className="mt-1 text-sm font-semibold text-slate-950">
            {trades.length - failingTrades} of {trades.length} trades passed every check
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            {/* The audit is built from the fixed ledger, so say so rather
                than let it read as a verdict on whichever variant is on
                screen. */}
            Covers the fixed ledger
            {variant === 'rrms' ? '; the RRMS ledger is not audited.' : '.'}
          </p>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">
            {trades.length - failingTrades} passed
          </span>
          {failingTrades > 0 && (
            <span className="rounded bg-rose-50 px-2 py-1 text-rose-700">
              {failingTrades} need review
            </span>
          )}
        </div>
      </div>

      {failures.length > 0 && (
        <div className="max-h-[320px] overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Trade</th>
                <th className="px-4 py-2 font-medium">Check</th>
                <th className="px-4 py-2 font-medium">Expected</th>
                <th className="px-4 py-2 font-medium">Actual</th>
              </tr>
            </thead>
            <tbody>
              {listed.map((failure) => (
                <tr
                  key={`${failure.trade_id}:${failure.check.check_id}`}
                  className="border-t border-slate-100"
                >
                  <td className="px-4 py-2 font-mono text-slate-500">{failure.trade_id}</td>
                  <td className="px-4 py-2 font-medium text-rose-700">
                    {failure.check.check_id}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-700">
                    {failure.check.expected || em}
                  </td>
                  <td className="px-4 py-2 font-mono text-slate-700">
                    {failure.check.actual || em}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {failures.length > listed.length && (
            <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
              {failures.length - listed.length} further failing checks not listed.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export function RunDetail({ entry, onClose }: RunDetailProps) {
  const hasRrms =
    entry.dataset_ids.includes('trades_rrms') && entry.dataset_ids.includes('performance_rrms');

  const [variant, setVariant] = useState<Variant>('fixed');
  const [status, setStatus] = useState<FetchStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tradesDataset, setTradesDataset] = useState<TradesDataset | null>(null);
  const [performanceDataset, setPerformanceDataset] = useState<PerformanceDataset | null>(null);

  // Fetched independently of the ledger and equity curve: an audit that
  // fails to load must not take the run view down with it, and a run whose
  // bundle predates the audit must still render.
  const audit = useRunAudit(entry.bundle_id, entry.dataset_ids.includes('trade_audit'));

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

          <LedgerAudit status={audit.status} dataset={audit.dataset} variant={variant} />

          <EquityChart points={equityPoints} variantLabel={variantLabel} />

          <TradeTable trades={trades} onFocusTrade={() => {}} />
        </>
      )}
    </div>
  );
}
