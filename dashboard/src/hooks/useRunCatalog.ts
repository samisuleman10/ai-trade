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

export type FetchStatus = 'loading' | 'loaded' | 'error';

export type PerformanceState = Record<
  string,
  { status: FetchStatus; summary?: PerformanceSummary; points?: PerformancePoint[] }
>;

export interface RunCatalogState {
  /** Status of the catalog (run list) fetch, not any individual run's data. */
  status: FetchStatus;
  entries: CatalogEntry[];
  /** Per-bundle `performance_fixed` fetch state, keyed by `bundle_id`. */
  performance: PerformanceState;
  /** Drop cached responses and fetch again. Backs the error states' retry control. */
  retry: () => void;
}

const PERFORMANCE_DATASET_ID = 'performance_fixed';

/**
 * Fetches the run catalog and every run's `performance_fixed` dataset.
 *
 * Both `RunCatalog` (grouped by strategy family) and `StrategyComparison`
 * (grouped by symbol, ranked by average R) need the same 48-request
 * fan-out over the same data -- this hook is the single place that fetch
 * loop lives, so it isn't duplicated between the two screens.
 */
export function useRunCatalog(): RunCatalogState {
  const [status, setStatus] = useState<FetchStatus>('loading');
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [performance, setPerformance] = useState<PerformanceState>({});
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    clearCatalogCache();
    setPerformance({});
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
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
  }, [attempt]);

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
    }

    return () => {
      cancelled = true;
    };
  }, [entries]);

  return { status, entries, performance, retry };
}
