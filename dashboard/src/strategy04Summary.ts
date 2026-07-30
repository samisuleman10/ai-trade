import { useEffect, useState } from 'react';
import { fetchDataset, fetchRuns } from './catalog';
import { familyOf } from './strategyDescriptions';
import type {
  DirectionMetrics,
  PerformanceMetrics,
  Strategy04Asset,
  Strategy04Result,
  Strategy04Version,
} from './strategy04Data';

/**
 * Assembles a Strategy04Result from the run's published datasets.
 *
 * These numbers used to be a hand-typed table in strategy04Data.ts. They
 * matched the bundles when written, but nothing kept them matching: a rerun
 * updated the ledger and left the screen quoting the previous run. The shape
 * is preserved exactly so every consumer of Strategy04Result is untouched.
 */

interface RunSummaryVariant {
  trades?: number;
  wins?: number;
  losses?: number;
  win_rate?: number;
  net_pnl?: number;
  average_r?: number;
  average_holding_hours?: number;
  maximum_consecutive_losses?: number;
  maximum_rrms_tier?: number;
  total_costs?: number;
  long?: { trades?: number; wins?: number; win_rate?: number };
  short?: { trades?: number; wins?: number; win_rate?: number };
  stop?: { trades?: number };
  target?: { trades?: number };
  weekend_close?: { trades?: number };
}

interface RunSummaryDataset {
  starting_equity: number | null;
  signals: { candidate: number | null; eligible: number | null };
  cost_model: {
    recorded: boolean;
    slippage_bps_per_side: number | null;
    commission_per_share_per_side: number | null;
  };
  data: {
    setup_bar_count: number | null;
    execution_bar_count: number | null;
    first_timestamp: string | null;
    last_timestamp: string | null;
  };
  variants: Record<string, RunSummaryVariant>;
}

interface PerformanceDataset {
  summary?: {
    trade_count?: number;
    wins?: number;
    losses?: number;
    win_rate?: number;
    net_pnl?: number;
    ending_equity?: number;
    profit_factor?: number;
    average_r?: number;
    max_drawdown?: number;
    long_trades?: number;
    short_trades?: number;
  };
}

const num = (value: number | undefined | null): number => (typeof value === 'number' ? value : 0);

function toMetrics(perf: PerformanceDataset, variant: RunSummaryVariant): PerformanceMetrics {
  const s = perf.summary ?? {};
  return {
    trades: num(s.trade_count),
    wins: num(s.wins),
    losses: num(s.losses),
    winRate: num(s.win_rate),
    netPnl: num(s.net_pnl),
    endingEquity: num(s.ending_equity),
    profitFactor: num(s.profit_factor),
    averageR: num(s.average_r),
    maxDrawdown: num(s.max_drawdown),
    longTrades: num(s.long_trades),
    shortTrades: num(s.short_trades),
    maximumConsecutiveLosses: num(variant.maximum_consecutive_losses),
    averageHoldingHours: num(variant.average_holding_hours),
    totalCosts: num(variant.total_costs),
    maximumRrmsTier: num(variant.maximum_rrms_tier),
  };
}

const toDirection = (side: RunSummaryVariant['long']): DirectionMetrics => ({
  trades: num(side?.trades),
  wins: num(side?.wins),
  winRate: num(side?.win_rate),
});

async function loadResult(
  version: string,
  asset: Strategy04Asset,
  variant: string,
  familyId: string,
): Promise<Strategy04Result | null> {
  const runs = await fetchRuns({ strategy_version: version, symbol: asset });
  const entry = runs.find((run) => {
    if (familyOf(run.run.strategy_id) !== familyId) return false;
    if (!run.dataset_ids.includes('run_summary')) return false;
    if (version === 'v1_2') return run.bundle_id.endsWith(`_${variant}`);
    return true;
  });
  if (!entry) return null;

  const [summary, fixed, rrms] = await Promise.all([
    fetchDataset<RunSummaryDataset>(entry.bundle_id, 'run_summary'),
    fetchDataset<PerformanceDataset>(entry.bundle_id, 'performance_fixed'),
    fetchDataset<PerformanceDataset>(entry.bundle_id, 'performance_rrms'),
  ]);

  const fixedVariant = summary.variants.fixed ?? {};
  const rrmsVariant = summary.variants.rrms ?? {};

  return {
    versionId: version as Strategy04Version,
    symbol: asset,
    startingEquity: num(summary.starting_equity),
    candidateSignals: num(summary.signals.candidate),
    eligibleSignals: num(summary.signals.eligible),
    directionStats: {
      long: toDirection(fixedVariant.long),
      short: toDirection(fixedVariant.short),
    },
    exitStats: {
      targets: num(fixedVariant.target?.trades),
      stops: num(fixedVariant.stop?.trades),
      weekendExits: num(fixedVariant.weekend_close?.trades),
    },
    dataRange: {
      first: summary.data.first_timestamp ?? '',
      last: summary.data.last_timestamp ?? '',
    },
    barCounts: {
      setup: num(summary.data.setup_bar_count),
      execution: num(summary.data.execution_bar_count),
    },
    fixed: toMetrics(fixed, fixedVariant),
    rrms: toMetrics(rrms, rrmsVariant),
  };
}

export type SummaryStatus = 'loading' | 'loaded' | 'error';

export const STRATEGY_04_ASSETS: Strategy04Asset[] = ['SPY', 'QQQ', 'DIA', 'EURUSD', 'GBPUSD'];

/**
 * Every asset's result for one version, keyed by symbol.
 *
 * Fetched as a set because the deep-dive's asset picker and its Compare
 * assets tab both need all five, and the catalog layer caches per URL, so
 * the second consumer costs nothing. `variant` only disambiguates v1_2
 * results (see loadResult); other versions ignore it, but it is still a
 * dependency here so switching variants while on v1_2 refetches.
 */
export function useStrategy04Results(
  version: string,
  variant: string,
  familyId: string,
): {
  status: SummaryStatus;
  results: Partial<Record<Strategy04Asset, Strategy04Result>>;
} {
  const [state, setState] = useState<{
    status: SummaryStatus;
    results: Partial<Record<Strategy04Asset, Strategy04Result>>;
  }>({ status: 'loading', results: {} });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', results: {} });

    Promise.all(
      STRATEGY_04_ASSETS.map((asset) => loadResult(version, asset, variant, familyId)),
    )
      .then((loaded) => {
        if (cancelled) return;
        const results: Partial<Record<Strategy04Asset, Strategy04Result>> = {};
        STRATEGY_04_ASSETS.forEach((asset, index) => {
          const result = loaded[index];
          if (result) results[asset] = result;
        });
        setState({ status: 'loaded', results });
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error', results: {} });
      });

    return () => {
      cancelled = true;
    };
  }, [version, variant, familyId]);

  return state;
}
