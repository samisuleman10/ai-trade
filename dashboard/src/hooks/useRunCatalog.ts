import { useCallback, useEffect, useState } from 'react';
import { clearCatalogCache, fetchDataset, fetchRuns } from '../catalog';
import type { CatalogEntry } from '../catalog';

/**
 * Shared shape for the `performance_fixed` dataset every run publishes.
 * Fields are optional because a producer may omit any of them -- callers
 * must render `—` rather than substitute 0 for anything missing.
 */
export interface PerformanceSummary {
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
  [key: string]: unknown;
}

export interface PerformancePoint {
  timestamp: string;
  equity: number;
  [key: string]: unknown;
}

export interface PerformanceDataset {
  summary?: PerformanceSummary;
  points?: PerformancePoint[];
}

/**
 * A run's declared cost model, or an explicit statement that it declared none.
 *
 * Only a minority of runs record a `backtest_configuration`, so `recorded:
 * false` is a real and common answer. Treating an unrecorded model as
 * equal to a recorded one would let the comparison screen present two runs
 * as like-for-like when only one of them stated its assumptions.
 */
export interface CostModel {
  recorded: boolean;
  slippage_bps_per_side: number | null;
  commission_per_share_per_side: number | null;
  /** Notional-based commission (FX runs); null when the run charged per share instead. */
  commission_bps_per_side: number | null;
  /** Floor applied under commission_bps_per_side; null when not recorded. */
  min_commission_per_order: number | null;
}

interface RunSummaryDataset {
  cost_model?: CostModel;
}

export type FetchStatus = 'loading' | 'loaded' | 'error';

export type PerformanceState = Record<
  string,
  { status: FetchStatus; summary?: PerformanceSummary; points?: PerformancePoint[] }
>;

export type CostModelState = Record<string, CostModel>;

export interface RunCatalogState {
  /** Status of the catalog (run list) fetch, not any individual run's data. */
  status: FetchStatus;
  entries: CatalogEntry[];
  /** Per-bundle `performance_fixed` fetch state, keyed by `bundle_id`. */
  performance: PerformanceState;
  /** Per-bundle declared cost model, keyed by `bundle_id`. Absent until fetched. */
  costModels: CostModelState;
  /** Drop cached responses and fetch again. Backs the error states' retry control. */
  retry: () => void;
}

const PERFORMANCE_DATASET_ID = 'performance_fixed';
const RUN_SUMMARY_DATASET_ID = 'run_summary';

/**
 * Fetches the run catalog and every run's `performance_fixed` dataset.
 *
 * Both `RunCatalog` (grouped by strategy family) and `StrategyComparison`
 * (grouped by symbol, ranked by average R) need the same 48-request
 * fan-out over the same data -- this hook is the single place that fetch
 * loop lives, so it isn't duplicated between the two screens.
 */
export function useRunCatalog(refreshToken = 0): RunCatalogState {
  const [status, setStatus] = useState<FetchStatus>('loading');
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [performance, setPerformance] = useState<PerformanceState>({});
  const [costModels, setCostModels] = useState<CostModelState>({});
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    clearCatalogCache();
    setPerformance({});
    setCostModels({});
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    // Drop per-run state as well: a run that disappeared from the catalog
    // would otherwise keep rendering its old numbers under a stale key.
    setPerformance({});
    setCostModels({});
    fetchRuns()
      .then((data) => {
        if (cancelled) return;
        setEntries(data);
        setStatus('loaded');
      })
      .catch(() => {
        if (cancelled) return;
        setStatus('error');
      });
    return () => {
      cancelled = true;
    };
    // refreshToken changes when the header's refresh control fires. Without
    // it, that control cleared the request cache but left every mounted
    // screen showing the state it had already fetched -- so the catalog only
    // appeared to refresh if you happened to navigate away and back.
  }, [attempt, refreshToken]);

  useEffect(() => {
    if (entries.length === 0) return;
    let cancelled = false;

    for (const entry of entries) {
      if (!entry.dataset_ids.includes(PERFORMANCE_DATASET_ID)) {
        setPerformance((prev) => ({ ...prev, [entry.bundle_id]: { status: 'error' } }));
        continue;
      }
      setPerformance((prev) => ({ ...prev, [entry.bundle_id]: { status: 'loading' } }));
      fetchDataset<PerformanceDataset>(entry.bundle_id, PERFORMANCE_DATASET_ID)
        .then((dataset) => {
          if (cancelled) return;
          setPerformance((prev) => ({
            ...prev,
            [entry.bundle_id]: { status: 'loaded', summary: dataset.summary, points: dataset.points },
          }));
        })
        .catch(() => {
          if (cancelled) return;
          setPerformance((prev) => ({ ...prev, [entry.bundle_id]: { status: 'error' } }));
        });

      if (entry.dataset_ids.includes(RUN_SUMMARY_DATASET_ID)) {
        fetchDataset<RunSummaryDataset>(entry.bundle_id, RUN_SUMMARY_DATASET_ID)
          .then((dataset) => {
            if (cancelled || !dataset.cost_model) return;
            setCostModels((prev) => ({ ...prev, [entry.bundle_id]: dataset.cost_model as CostModel }));
          })
          .catch(() => undefined);
      }
    }

    return () => {
      cancelled = true;
    };
  }, [entries]);

  return { status, entries, performance, costModels, retry };
}
