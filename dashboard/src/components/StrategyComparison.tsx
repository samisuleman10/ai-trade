import { useMemo } from 'react';
import { AlertTriangle } from 'lucide-react';
import type { CatalogEntry } from '../catalog';
import { familyOf } from '../strategyDescriptions';
import { useRunCatalog } from '../hooks/useRunCatalog';
import type { PerformancePoint, PerformanceSummary } from '../hooks/useRunCatalog';

interface StrategyComparisonProps {
  onSelectRun?: (entry: CatalogEntry) => void;
}

/**
 * Below this many trades, a run's average R is too noisy to trust: a
 * handful of trades can swing the average wildly, and win rate / profit
 * factor are built from the same small sample. 30 is a commonly used rule
 * of thumb for "enough trades that the average has started to settle" --
 * it is not a statistically derived cutoff for this dataset, just a
 * stated heuristic so small-sample runs are visibly flagged instead of
 * silently ranked alongside runs with hundreds of trades.
 */
const SMALL_SAMPLE_THRESHOLD = 30;

const UNKNOWN_SYMBOL_KEY = '__unknown__';
const UNKNOWN_SYMBOL_LABEL = 'Symbol not recorded';

const em = '—';

function familyLabel(family: string): string {
  const match = family.match(/^strategy_(\d+)$/);
  return match ? `Strategy ${match[1]}` : family;
}

const netPnl = (value: unknown): string =>
  typeof value === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
        signDisplay: 'always',
      }).format(value)
    : em;

const winRate = (value: unknown): string => (typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : em);

const ratio = (value: unknown): string => (typeof value === 'number' ? value.toFixed(2) : em);

const count = (value: unknown): string => (typeof value === 'number' ? String(value) : em);

const averageR = (value: unknown): string =>
  typeof value === 'number' ? `${value >= 0 ? '+' : ''}${value.toFixed(3)}R` : em;

const dateOnly = (value: string | undefined): string | null => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parsed);
};

function dateRangeLabel(points: PerformancePoint[] | undefined): string {
  if (!points || points.length === 0) return em;
  const first = dateOnly(points[0]?.timestamp);
  const last = dateOnly(points[points.length - 1]?.timestamp);
  if (!first || !last) return em;
  return first === last ? first : `${first} – ${last}`;
}

interface ComparisonRow {
  entry: CatalogEntry;
  summary?: PerformanceSummary;
  points?: PerformancePoint[];
  isSmallSample: boolean;
}

/** Symbol used to group a run, or the sentinel key for "not recorded". */
function symbolKeyOf(entry: CatalogEntry): string {
  const symbol = entry.instrument.symbol;
  return symbol ? symbol : UNKNOWN_SYMBOL_KEY;
}

export function StrategyComparison({ onSelectRun }: StrategyComparisonProps) {
  const { status, entries, performance, retry } = useRunCatalog();

  const groups = useMemo(() => {
    const bySymbol = new Map<string, ComparisonRow[]>();
    for (const entry of entries) {
      const key = symbolKeyOf(entry);
      const summary = performance[entry.bundle_id]?.summary;
      const points = performance[entry.bundle_id]?.points;
      const row: ComparisonRow = {
        entry,
        summary,
        points,
        isSmallSample:
          typeof summary?.trade_count === 'number' && summary.trade_count < SMALL_SAMPLE_THRESHOLD,
      };
      const list = bySymbol.get(key);
      if (list) {
        list.push(row);
      } else {
        bySymbol.set(key, [row]);
      }
    }

    for (const rows of bySymbol.values()) {
      rows.sort((a, b) => {
        const rA = a.summary?.average_r;
        const rB = b.summary?.average_r;
        const hasA = typeof rA === 'number';
        const hasB = typeof rB === 'number';
        // Runs without a computed average R can't be ranked at all --
        // they sink to the bottom of their group rather than being
        // dropped or sorted as if their average were 0.
        if (hasA && hasB) return rB - rA;
        if (hasA) return -1;
        if (hasB) return 1;
        return a.entry.bundle_id.localeCompare(b.entry.bundle_id);
      });
    }

    // Known symbols alphabetically first, "Symbol not recorded" last.
    return Array.from(bySymbol.entries()).sort(([a], [b]) => {
      if (a === UNKNOWN_SYMBOL_KEY) return 1;
      if (b === UNKNOWN_SYMBOL_KEY) return -1;
      return a.localeCompare(b);
    });
  }, [entries, performance]);

  if (status === 'loading') {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">Compare strategies</div>
        <p className="mt-2 text-sm text-slate-600">Loading run catalog…</p>
      </section>
    );
  }

  if (status === 'error') {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">Compare strategies</div>
        <div className="mt-2 text-sm font-semibold text-slate-900">Catalog API unreachable</div>
        <p className="mt-2 text-xs text-slate-500">
          Start it with <code>python -m ai_trade.server --port 8080</code>, then retry.
        </p>
        <button type="button" className="s4-button mt-4" onClick={retry}>
          Retry
        </button>
      </section>
    );
  }

  if (entries.length === 0) {
    return (
      <section className="s4-panel p-8 text-center">
        <div className="s4-eyebrow">Compare strategies</div>
        <p className="mt-2 text-sm text-slate-600">The API is reachable but reported no discovered runs.</p>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <section className="s4-panel flex items-start gap-3 p-5">
        <div className="s4-evidence-icon">
          <AlertTriangle size={18} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-950">Why average R, and why grouped by symbol</div>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Runs span different instruments, periods and trade counts -- one run has a single trade
            over two days, another has nearly 800 trades over five years. Ranking those by net P&amp;L
            would just reward whichever run traded the most or the longest. Average R (result per trade,
            in units of initial risk) is scale-free, so it survives differing sample sizes and time
            windows and is comparable within the same instrument. Net P&amp;L is still shown for context,
            never used to rank.
          </p>
        </div>
      </section>

      {groups.map(([symbolKey, rows]) => {
        const isUnknown = symbolKey === UNKNOWN_SYMBOL_KEY;
        return (
          <section key={symbolKey} className="s4-panel overflow-hidden">
            <div className="border-b border-slate-200 px-5 py-4">
              <div className="s4-eyebrow">{isUnknown ? UNKNOWN_SYMBOL_LABEL : symbolKey}</div>
              <h2 className="mt-1 text-base font-semibold text-slate-950">
                {rows.length} run{rows.length === 1 ? '' : 's'} ranked by average R
              </h2>
              {isUnknown && (
                <p className="mt-1 max-w-3xl text-xs text-slate-500">
                  These runs' manifests never recorded an instrument symbol. Shown separately rather
                  than guessed or dropped.
                </p>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="s4-compare-table min-w-[1080px]">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Strategy ID / version</th>
                    <th>Avg R</th>
                    <th>Win rate</th>
                    <th>Profit factor</th>
                    <th>Net P&amp;L</th>
                    <th>Trades</th>
                    <th>Date range</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ entry, summary, points, isSmallSample }) => (
                    <tr
                      key={entry.bundle_id}
                      className="s4-row-button hover:bg-indigo-50/50"
                      tabIndex={0}
                      role="button"
                      aria-label={`Open ${entry.run.strategy_id} ${entry.run.strategy_version} on ${
                        entry.instrument.symbol || 'unknown symbol'
                      }`}
                      onClick={() => onSelectRun?.(entry)}
                      onKeyDown={(event) => {
                        if (event.key !== 'Enter' && event.key !== ' ') return;
                        event.preventDefault();
                        onSelectRun?.(entry);
                      }}
                    >
                      <td>{familyLabel(familyOf(entry.run.strategy_id))}</td>
                      <td>
                        <div className="font-semibold text-slate-950">{entry.run.strategy_version}</div>
                        <div className="mt-0.5 text-[11px] font-normal text-slate-500">
                          {entry.run.strategy_id}
                        </div>
                      </td>
                      <td
                        className={
                          typeof summary?.average_r === 'number'
                            ? summary.average_r >= 0
                              ? 'text-emerald-700'
                              : 'text-rose-700'
                            : undefined
                        }
                      >
                        <span className="inline-flex items-center justify-end gap-1.5">
                          {isSmallSample && (
                            <span
                              title={`Fewer than ${SMALL_SAMPLE_THRESHOLD} trades -- sample too small to rank confidently.`}
                              aria-label={`Small sample: fewer than ${SMALL_SAMPLE_THRESHOLD} trades`}
                              className="s4-small-sample-flag"
                            >
                              <AlertTriangle size={12} />
                            </span>
                          )}
                          {averageR(summary?.average_r)}
                        </span>
                      </td>
                      <td>{winRate(summary?.win_rate)}</td>
                      <td>{ratio(summary?.profit_factor)}</td>
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
                      <td>{count(summary?.trade_count)}</td>
                      <td className="whitespace-nowrap font-normal">{dateRangeLabel(points)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
