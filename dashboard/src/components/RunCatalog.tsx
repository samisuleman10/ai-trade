import { useEffect, useMemo, useState } from 'react';
import { fetchDataset, fetchRuns } from '../catalog';
import type { CatalogEntry } from '../catalog';

interface PerformanceSummary {
  trade_count?: number;
  net_pnl?: number;
  win_rate?: number;
  profit_factor?: number;
  max_drawdown?: number;
  [key: string]: unknown;
}

interface PerformanceDataset {
  summary?: PerformanceSummary;
}

interface RunCatalogProps {
  onSelectRun?: (entry: CatalogEntry) => void;
}

type FetchStatus = 'loading' | 'loaded' | 'error';

type MetricsState = Record<string, { status: FetchStatus; summary?: PerformanceSummary }>;

const PERFORMANCE_DATASET_ID = 'performance_fixed';
const FAMILY_RE = /^strategy_\d+/;

function familyOf(strategyId: string): string {
  const match = strategyId.match(FAMILY_RE);
  return match ? match[0] : strategyId;
}

function familyLabel(family: string): string {
  const match = family.match(/^strategy_(\d+)$/);
  return match ? `Strategy ${match[1]}` : family;
}

const em = '—';

const netPnl = (value: unknown): string =>
  typeof value === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
        signDisplay: 'always',
      }).format(value)
    : em;

const drawdown = (value: unknown): string =>
  typeof value === 'number'
    ? `-${new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }).format(Math.abs(value))}`
    : em;

const winRate = (value: unknown): string => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : em);

const ratio = (value: unknown): string => (typeof value === 'number' ? value.toFixed(2) : em);

const count = (value: unknown): string => (typeof value === 'number' ? String(value) : em);

export function RunCatalog({ onSelectRun }: RunCatalogProps) {
  const [status, setStatus] = useState<FetchStatus>('loading');
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [metrics, setMetrics] = useState<MetricsState>({});
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null);

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
  }, []);

  useEffect(() => {
    if (entries.length === 0) return;
    let cancelled = false;

    for (const entry of entries) {
      if (!entry.dataset_ids.includes(PERFORMANCE_DATASET_ID)) {
        setMetrics((prev) => ({ ...prev, [entry.bundle_id]: { status: 'error' } }));
        continue;
      }
      setMetrics((prev) => ({ ...prev, [entry.bundle_id]: { status: 'loading' } }));
      fetchDataset<PerformanceDataset>(entry.bundle_id, PERFORMANCE_DATASET_ID)
        .then((dataset) => {
          if (cancelled) return;
          setMetrics((prev) => ({
            ...prev,
            [entry.bundle_id]: { status: 'loaded', summary: dataset.summary },
          }));
        })
        .catch(() => {
          if (cancelled) return;
          setMetrics((prev) => ({ ...prev, [entry.bundle_id]: { status: 'error' } }));
        });
    }

    return () => {
      cancelled = true;
    };
  }, [entries]);

  const groups = useMemo(() => {
    const byFamily = new Map<string, CatalogEntry[]>();
    for (const entry of entries) {
      const family = familyOf(entry.run.strategy_id);
      const list = byFamily.get(family);
      if (list) {
        list.push(entry);
      } else {
        byFamily.set(family, [entry]);
      }
    }
    for (const list of byFamily.values()) {
      list.sort((a, b) => {
        if (a.run.strategy_id !== b.run.strategy_id) {
          return a.run.strategy_id.localeCompare(b.run.strategy_id);
        }
        const symbolA = a.instrument.symbol ?? '';
        const symbolB = b.instrument.symbol ?? '';
        if (symbolA !== symbolB) return symbolA.localeCompare(symbolB);
        return a.bundle_id.localeCompare(b.bundle_id);
      });
    }
    return Array.from(byFamily.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [entries]);

  if (status === 'loading') {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">All runs</div>
        <p className="mt-2 text-sm text-slate-600">Loading run catalog…</p>
      </section>
    );
  }

  if (status === 'error') {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">All runs</div>
        <div className="mt-2 text-sm font-semibold text-slate-900">Catalog API unreachable</div>
        <p className="mt-2 text-xs text-slate-500">
          Start it with <code>python -m ai_trade.server --port 8080</code>, then reopen this tab.
        </p>
      </section>
    );
  }

  if (entries.length === 0) {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">All runs</div>
        <p className="mt-2 text-sm text-slate-600">The API is reachable but reported no discovered runs.</p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      {groups.map(([family, familyEntries]) => (
        <section key={family} className="s4-panel overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <div className="s4-eyebrow">{familyLabel(family)}</div>
            <h2 className="mt-1 text-base font-semibold text-slate-950">
              {familyEntries.length} run{familyEntries.length === 1 ? '' : 's'} discovered
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="s4-compare-table min-w-[980px]">
              <thead>
                <tr>
                  <th>Strategy ID / version</th>
                  <th>Symbol</th>
                  <th>Mode</th>
                  <th>Trades</th>
                  <th>Net P&amp;L</th>
                  <th>Win rate</th>
                  <th>Profit factor</th>
                  <th>Max drawdown</th>
                </tr>
              </thead>
              <tbody>
                {familyEntries.map((entry) => {
                  const summary = metrics[entry.bundle_id]?.summary;
                  const isSelected = entry.bundle_id === selectedBundleId;
                  return (
                    <tr
                      key={entry.bundle_id}
                      className={`cursor-pointer hover:bg-indigo-50/50 ${isSelected ? 'bg-indigo-50/50' : ''}`}
                      onClick={() => {
                        setSelectedBundleId(entry.bundle_id);
                        onSelectRun?.(entry);
                      }}
                    >
                      <td>
                        <div className="font-semibold text-slate-950">{entry.run.strategy_version}</div>
                        <div className="mt-0.5 text-[11px] font-normal text-slate-500">{entry.run.strategy_id}</div>
                      </td>
                      <td>{entry.instrument.symbol || em}</td>
                      <td>{entry.mode || em}</td>
                      <td>{count(summary?.trade_count)}</td>
                      <td
                        className={
                          typeof summary?.net_pnl === 'number'
                            ? summary.net_pnl >= 0
                              ? 'text-emerald-700'
                              : 'text-rose-700'
                            : undefined
                        }
                      >
                        {netPnl(summary?.net_pnl)}
                      </td>
                      <td>{winRate(summary?.win_rate)}</td>
                      <td>{ratio(summary?.profit_factor)}</td>
                      <td className={typeof summary?.max_drawdown === 'number' ? 'text-rose-700' : undefined}>
                        {drawdown(summary?.max_drawdown)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
