import { useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Check,
  ChevronRight,
  Database,
  FlaskConical,
  Scale,
  TrendingUp,
} from 'lucide-react';
import { useStrategy04Audit } from './strategy04Audit';
import { STRATEGY_04_ASSETS, useStrategy04Results } from './strategy04Summary';
import {
  STRATEGY_04_SPECS,
  STRATEGY_04_VARIANTS,
  STRATEGY_04_VERSIONS,
} from './strategy04Data';
import type {
  PerformanceMetrics,
  Strategy04Asset,
  Strategy04Result,
  Strategy04Variant,
  Strategy04Version,
} from './strategy04Data';
import { AssetComparison } from './components/AssetComparison';
import { AuditedTradeList } from './components/AuditedTradeList';
import { TradeSetupChart } from './components/TradeSetupChart';
import { TradeExecutionChart } from './components/TradeExecutionChart';

type View = 'performance' | 'comparison' | 'rules' | 'chart';

const money = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

const preciseMoney = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

const percent = (value: number, digits = 2) => `${value.toFixed(digits)}%`;

const dateLabel = (value: string) =>
  new Intl.DateTimeFormat('en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value));

function ModeCard({
  title,
  subtitle,
  metrics,
  startingEquity,
  tone,
}: {
  title: string;
  subtitle: string;
  metrics: PerformanceMetrics;
  startingEquity: number;
  tone: 'fixed' | 'rrms';
}) {
  const returnPct = (metrics.netPnl / startingEquity) * 100;
  const drawdownPct = (metrics.maxDrawdown / startingEquity) * 100;
  const positive = metrics.netPnl >= 0;

  return (
    <article className={`s4-mode-card ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="s4-mode-label">{title}</span>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>
        <span className={`s4-status-dot ${positive ? 'positive' : 'negative'}`}>
          {positive ? 'Positive' : 'Negative'}
        </span>
      </div>

      <div className="mt-6">
        <div className={`font-mono text-3xl font-semibold tracking-tight ${positive ? 'text-emerald-700' : 'text-rose-700'}`}>
          {preciseMoney(metrics.netPnl)}
        </div>
        <div className={`mt-1 text-sm font-semibold ${positive ? 'text-emerald-700' : 'text-rose-700'}`}>
          {returnPct >= 0 ? '+' : ''}{percent(returnPct)} return
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-5 gap-y-4 border-t border-slate-200 pt-5">
        <div>
          <dt>Profit factor</dt>
          <dd className={metrics.profitFactor >= 1 ? 'text-slate-950' : 'text-rose-700'}>
            {metrics.profitFactor.toFixed(2)}
          </dd>
        </div>
        <div>
          <dt>Max drawdown</dt>
          <dd className="text-rose-700">-{money(metrics.maxDrawdown)}</dd>
          <span>{percent(drawdownPct)} of capital</span>
        </div>
        <div>
          <dt>Ending equity</dt>
          <dd>{money(metrics.endingEquity)}</dd>
        </div>
        <div>
          <dt>Modeled costs</dt>
          <dd>{preciseMoney(metrics.totalCosts)}</dd>
        </div>
        <div>
          <dt>{tone === 'rrms' ? 'Highest RRMS tier' : 'Risk per trade'}</dt>
          <dd>{tone === 'rrms' ? `Tier ${metrics.maximumRrmsTier + 1}` : '0.15%'}</dd>
        </div>
      </dl>
    </article>
  );
}

function PerformanceOverview({ result }: { result: Strategy04Result }) {
  const fixedReturn = (result.fixed.netPnl / result.startingEquity) * 100;
  const rrmsReturn = (result.rrms.netPnl / result.startingEquity) * 100;

  const comparisonRows = [
    {
      label: 'Net P&L',
      fixed: preciseMoney(result.fixed.netPnl),
      rrms: preciseMoney(result.rrms.netPnl),
    },
    {
      label: 'Return on $100k',
      fixed: `${fixedReturn >= 0 ? '+' : ''}${percent(fixedReturn)}`,
      rrms: `${rrmsReturn >= 0 ? '+' : ''}${percent(rrmsReturn)}`,
    },
    {
      label: 'Profit factor',
      fixed: result.fixed.profitFactor.toFixed(3),
      rrms: result.rrms.profitFactor.toFixed(3),
    },
    {
      label: 'Maximum drawdown',
      fixed: preciseMoney(result.fixed.maxDrawdown),
      rrms: preciseMoney(result.rrms.maxDrawdown),
    },
  ];

  return (
    <div className="space-y-5">
      <section className="s4-panel flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="s4-eyebrow">Shared trade results</div>
          <h2 className="mt-1 text-sm font-semibold text-slate-950">Signal funnel and outcomes</h2>
          <p className="mt-1 text-[11px] text-slate-500">
            Identical for Fixed and RRMS because both use the same trades.
          </p>
        </div>

        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs" aria-label="Signal funnel">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Candidates</span>
            <strong className="ml-2 font-mono text-base text-slate-950">{result.candidateSignals}</strong>
          </div>
          <ArrowRight size={15} className="text-slate-300" />
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Eligible</span>
            <strong className="ml-2 font-mono text-base text-slate-950">{result.eligibleSignals}</strong>
          </div>
          <ArrowRight size={15} className="text-slate-300" />
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Completed</span>
            <strong className="ml-2 font-mono text-base text-slate-950">{result.fixed.trades}</strong>
          </div>
          </div>
          <div className="mt-2 text-right text-[11px] text-slate-500">
            <span className="font-semibold text-slate-700">Exit results</span>
            <span className="mx-2 text-slate-300">·</span>
            {result.exitStats.targets} targets · {result.exitStats.stops} stops · {result.exitStats.weekendExits} weekend exits
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {[
          ['Win rate', percent(result.fixed.winRate * 100, 1), 'Same for both sizing modes'],
          ['Trades', result.fixed.trades.toString(), `${result.fixed.wins} wins · ${result.fixed.losses} losses`],
          ['Long trades', result.directionStats.long.trades.toString(), `${result.directionStats.long.wins} wins · ${percent(result.directionStats.long.winRate * 100, 1)} win rate`],
          ['Short trades', result.directionStats.short.trades.toString(), `${result.directionStats.short.wins} wins · ${percent(result.directionStats.short.winRate * 100, 1)} win rate`],
          ['Avg result / trade', `${result.fixed.averageR >= 0 ? '+' : ''}${result.fixed.averageR.toFixed(3)}R`, `${result.fixed.averageR >= 0 ? 'Earned' : 'Lost'} ${Math.abs(result.fixed.averageR * 100).toFixed(1)}% of initial risk per trade`],
          ['Average hold', `${result.fixed.averageHoldingHours.toFixed(1)}h`, 'Entry to completed exit'],
          ['Max loss streak', result.fixed.maximumConsecutiveLosses.toString(), 'Longest run of losing trades'],
        ].map(([label, value, note]) => (
          <article key={label} className="s4-stat-card">
            <div className="s4-eyebrow">{label}</div>
            <div className="mt-1 font-mono text-lg font-semibold text-slate-950">{value}</div>
            <div className="mt-1 text-[11px] leading-4 text-slate-500">{note}</div>
          </article>
        ))}
      </section>

      <section className="s4-panel flex items-start gap-3 p-5">
        <div className="s4-evidence-icon"><Scale size={18} /></div>
        <div>
          <div className="text-sm font-semibold text-slate-950">How to read the sizing results</div>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Fixed risks 0.15% on every trade and is the strategy baseline. RRMS uses the same trades in the same order, but changes the risk tier after each outcome.
          </p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <ModeCard
          title="Fixed 0.15%"
          subtitle="Primary strategy-edge baseline"
          metrics={result.fixed}
          startingEquity={result.startingEquity}
          tone="fixed"
        />
        <ModeCard
          title="RRMS"
          subtitle="Progressive, path-dependent position sizing"
          metrics={result.rrms}
          startingEquity={result.startingEquity}
          tone="rrms"
        />
      </div>

      <section className="s4-panel">
        <div className="border-b border-slate-200 px-5 py-4">
          <div className="s4-eyebrow">Direct comparison</div>
          <h2 className="mt-1 text-base font-semibold text-slate-950">What changes when sizing changes?</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="s4-compare-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Fixed 0.15%</th>
                <th>RRMS</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td>{row.fixed}</td>
                  <td>{row.rrms}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

    </div>
  );
}

const CHANGE_FROM_LABEL: Record<Strategy04Version, string> = {
  v1: 'Change from v1.0:',
  v1_1: 'Change from v1.0:',
  v1_2: 'Change from v1.1:',
};

function RulesView({ version }: { version: Strategy04Version }) {
  const spec = STRATEGY_04_SPECS[version];

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-5">
        <section className="s4-panel p-6">
          <div className="s4-eyebrow">Implemented specification</div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-950">{spec.title}</h2>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-600">{spec.hypothesis}</p>
          {spec.changeFromPrior && (
            <div className="mt-5 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm leading-6 text-indigo-950">
              <strong>{CHANGE_FROM_LABEL[version]}</strong> {spec.changeFromPrior}
            </div>
          )}
        </section>

        <div className="grid gap-4 lg:grid-cols-2">
          {spec.ruleGroups.map((group, index) => (
            <section key={group.title} className="s4-panel p-5">
              <div className="flex items-start gap-3">
                <span className="s4-rule-number">{index + 1}</span>
                <div>
                  <h3 className="text-sm font-semibold text-slate-950">{group.title}</h3>
                  <p className="mt-1 text-xs text-slate-500">{group.subtitle}</p>
                </div>
              </div>
              <ul className="mt-5 space-y-3">
                {group.rules.map((rule) => (
                  <li key={rule} className="flex gap-3 text-sm leading-5 text-slate-700">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{rule}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>

      <aside className="space-y-4">
        <section className="s4-panel p-5">
          <div className="s4-eyebrow">Timeframe contract</div>
          <div className="mt-5 flex items-center gap-3">
            <div className="s4-timeframe-node">
              <strong>1H</strong>
              <span>Zones</span>
            </div>
            <ArrowRight className="text-slate-400" size={18} />
            <div className="s4-timeframe-node active">
              <strong>15M</strong>
              <span>Reaction</span>
            </div>
          </div>
          <p className="mt-4 text-xs leading-5 text-slate-500">
            Strategy 04 currently has saved 1H/15M results. A 4H/1H profile is not yet produced and is not shown as tested.
          </p>
        </section>

        <section className="s4-panel p-5">
          <div className="s4-eyebrow">Risk policy</div>
          <p className="mt-3 text-sm leading-6 text-slate-700">{spec.riskPolicy}</p>
        </section>

        <section className="s4-panel p-5">
          <div className="s4-eyebrow">Verification</div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Non-repainting</dt>
              <dd className="font-semibold text-emerald-700">Passed</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Trading mode</dt>
              <dd className="font-semibold text-slate-800">Historical only</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Orders generated</dt>
              <dd className="font-mono font-semibold text-emerald-700">0</dd>
            </div>
          </dl>
        </section>
      </aside>
    </div>
  );
}

/**
 * Strategy 04 deep dive: version/asset switchers, the S04 stat tiles, and
 * the Performance / Compare assets / Rules / Chart & trades tabs. This
 * used to be the whole dashboard (header, top-level nav and all); it is
 * now mounted as one section inside `App`, which owns the shell chrome
 * (header, cross-strategy top-level nav, footer) instead.
 */
export default function Strategy04Dashboard() {
  const [version, setVersion] = useState<Strategy04Version>('v1_1');
  const [asset, setAsset] = useState<Strategy04Asset>('SPY');
  const [variant, setVariant] = useState<Strategy04Variant>('base');
  const [view, setView] = useState<View>('performance');
  const { status: summaryStatus, results } = useStrategy04Results(version, variant);
  const result = results[asset];
  const { status: auditStatus, trades: auditedTrades } = useStrategy04Audit(version, asset, variant);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const selectedTrade = useMemo(
    () => auditedTrades.find((trade) => trade.trade_id === selectedTradeId) ?? auditedTrades[0] ?? null,
    [auditedTrades, selectedTradeId],
  );

  if (!result) {
    const label = version === 'v1_2' ? `${version} (${variant})` : version;
    return (
      <section className="s4-panel p-8 text-center">
        <div className="text-sm font-semibold text-slate-900">
          {summaryStatus === 'loading'
            ? `Loading the ${asset} ${label} run…`
            : summaryStatus === 'error'
              ? 'Catalog API unreachable'
              : `No published run for ${asset} ${label}.`}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {summaryStatus === 'loading'
            ? 'Summary metrics are read from the published run, not stored in the page.'
            : summaryStatus === 'error'
              ? 'Start it with python -m ai_trade.server --port 8080, then reload.'
              : 'Pick a different asset, version, or variant -- this combination has no published bundle.'}
        </p>
      </section>
    );
  }

  return (
    <>
      <section className="s4-context-panel">
        <div className="flex min-w-0 items-center gap-3">
          <div className="s4-strategy-code">S4</div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-slate-950">Strategy 04</div>
            <div className="truncate text-xs text-slate-500">Causal 1H zones · 15M reaction entries</div>
          </div>
        </div>

        <div className="s4-context-divider" />

        <div>
          <div className="s4-control-label">Version</div>
          <div className="s4-segment mt-1.5">
            {STRATEGY_04_VERSIONS.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={version === item.id}
                onClick={() => setVersion(item.id)}
                className={version === item.id ? 'is-active' : ''}
                title={item.description}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {version === 'v1_2' && (
          <div>
            <div className="s4-control-label">Variant</div>
            <div className="s4-segment mt-1.5">
              {STRATEGY_04_VARIANTS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={variant === item.id}
                  onClick={() => setVariant(item.id)}
                  className={variant === item.id ? 'is-active' : ''}
                  title={item.description}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="s4-control-label">Asset</div>
          <div className="s4-segment mt-1.5">
            {STRATEGY_04_ASSETS.map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={asset === item}
                onClick={() => setAsset(item)}
                className={asset === item ? 'is-active' : ''}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="s4-context-divider hidden xl:block" />

        <div className="s4-timeframe-flow">
          <div>
            <span>Setup</span>
            <strong>1H zones</strong>
          </div>
          <ChevronRight size={17} />
          <div>
            <span>Trigger & entry</span>
            <strong>15M reaction</strong>
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="s4-context-stat">
          <Database size={16} />
          <div>
            <span>Dataset window</span>
            <strong>{dateLabel(result.dataRange.first)} — {dateLabel(result.dataRange.last)}</strong>
          </div>
        </div>
        <div className="s4-context-stat">
          <BarChart3 size={16} />
          <div>
            <span>Completed bars</span>
            <strong>{result.barCounts.setup.toLocaleString()} 1H · {result.barCounts.execution.toLocaleString()} 15M</strong>
          </div>
        </div>
        <div className="s4-context-stat">
          <FlaskConical size={16} />
          <div>
            <span>Signal funnel</span>
            <strong>{result.candidateSignals} candidates · {result.eligibleSignals} eligible</strong>
          </div>
        </div>
        <div className="s4-context-stat">
          <Scale size={16} />
          <div>
            <span>Sizing comparison</span>
            <strong>Fixed 0.15% vs RRMS</strong>
          </div>
        </div>
      </section>

      <nav className="s4-tabs mt-6" aria-label="Strategy 04 sections">
        {[
          { id: 'performance' as const, label: 'Performance', icon: TrendingUp },
          { id: 'comparison' as const, label: 'Compare assets', icon: BarChart3 },
          { id: 'rules' as const, label: 'Rules', icon: BookOpen },
          { id: 'chart' as const, label: 'Chart & trades', icon: Activity },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            aria-current={view === id ? 'page' : undefined}
            onClick={() => setView(id)}
            className={view === id ? 'is-active' : ''}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      <div className="mt-5">
        {view === 'performance' && <PerformanceOverview result={result} />}
        {view === 'comparison' && (
          <AssetComparison
            version={version}
            results={results}
            selectedAsset={asset}
            onSelectAsset={(nextAsset) => {
              setAsset(nextAsset);
              setView('performance');
            }}
          />
        )}
        {view === 'rules' && <RulesView version={version} />}
        {view === 'chart' && (
          <div className="space-y-5">
            {auditStatus === 'loading' ? (
              <section className="s4-panel p-8 text-center">
                <div className="text-sm font-semibold text-slate-900">
                  Loading the {asset} {version === 'v1_2' ? `${version} (${variant})` : version} audit…
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Each audit carries a bar window per trade, so it is fetched on demand
                  rather than shipped in the initial page.
                </p>
              </section>
            ) : auditStatus === 'error' ? (
              <section className="s4-panel p-8 text-center">
                <div className="text-sm font-semibold text-slate-900">Catalog API unreachable</div>
                <p className="mt-2 text-xs text-slate-500">
                  Start it with <code>python -m ai_trade.server --port 8080</code>, then reopen
                  this tab. Nothing is shown from a stale copy.
                </p>
              </section>
            ) : auditedTrades.length === 0 ? (
              <section className="s4-panel p-8 text-center">
                <div className="text-sm font-semibold text-slate-900">
                  No published audit for {asset} {version === 'v1_2' ? `${version} (${variant})` : version}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Run <code>python -m ai_trade.backfill_visualization_bundles</code> to publish
                  this run's audit datasets.
                </p>
              </section>
            ) : (
              <>
                <AuditedTradeList
                  trades={auditedTrades}
                  selectedTradeId={selectedTrade ? selectedTrade.trade_id : null}
                  onSelect={setSelectedTradeId}
                />
                {selectedTrade && (
                  <>
                    <TradeSetupChart trade={selectedTrade} />
                    <TradeExecutionChart trade={selectedTrade} />
                  </>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
