import { STRATEGY_04_RESULTS } from '../strategy04Data';
import type {
  Strategy04Asset,
  Strategy04Version,
} from '../strategy04Data';

interface AssetComparisonProps {
  version: Strategy04Version;
  selectedAsset: Strategy04Asset;
  onSelectAsset: (asset: Strategy04Asset) => void;
}

const assets: Strategy04Asset[] = ['SPY', 'DIA', 'QQQ'];

const labels: Record<Strategy04Asset, string> = {
  SPY: 'SPY / US500 proxy',
  DIA: 'DIA / US30 proxy',
  QQQ: 'QQQ / US100 proxy',
};

const money = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
    signDisplay: 'always',
  }).format(value);

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export function AssetComparison({
  version,
  selectedAsset,
  onSelectAsset,
}: AssetComparisonProps) {
  const rows = assets.map((asset) => {
    const result = STRATEGY_04_RESULTS[version][asset];
    const promising =
      result.fixed.profitFactor >= 1.2 && result.fixed.averageR > 0;

    return { asset, result, promising };
  });

  return (
    <section className="s4-panel overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="s4-eyebrow">Cross-asset summary</div>
          <h2 className="mt-1 text-base font-semibold text-slate-950">
            Strategy 04 · {version === 'v1_1' ? 'v1.1' : 'v1.0'}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Same 1H-zone and 15M-entry profile across every instrument.
          </p>
        </div>
        <div className="text-[11px] text-slate-500">
          Starting equity: <strong className="text-slate-700">$100,000 per instrument</strong>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="s4-compare-table min-w-[860px]">
          <thead>
            <tr>
              <th>Instrument</th>
              <th>Fixed P&amp;L</th>
              <th>Win rate</th>
              <th>Profit factor</th>
              <th>Avg result</th>
              <th>RRMS P&amp;L</th>
              <th>Research verdict</th>
              <th aria-label="Open instrument" />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ asset, result, promising }) => (
              <tr
                key={asset}
                className={asset === selectedAsset ? 'bg-indigo-50/50' : undefined}
              >
                <td>
                  <div className="font-semibold text-slate-950">{labels[asset]}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">
                    {result.fixed.trades} completed trades
                  </div>
                </td>
                <td className={result.fixed.netPnl >= 0 ? 'text-emerald-700' : 'text-rose-700'}>
                  {money(result.fixed.netPnl)}
                </td>
                <td>{percent(result.fixed.winRate)}</td>
                <td>{result.fixed.profitFactor.toFixed(2)}</td>
                <td>
                  {result.fixed.averageR >= 0 ? '+' : ''}
                  {result.fixed.averageR.toFixed(3)}R
                </td>
                <td className={result.rrms.netPnl >= 0 ? 'text-emerald-700' : 'text-rose-700'}>
                  {money(result.rrms.netPnl)}
                </td>
                <td>
                  <span className={`s4-status-dot ${promising ? 'positive' : 'negative'}`}>
                    {promising ? 'Promising' : 'Not trade-ready'}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    className="text-xs font-semibold text-indigo-700 hover:text-indigo-900"
                    onClick={() => onSelectAsset(asset)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-slate-200 bg-slate-50 px-5 py-3 text-[11px] leading-5 text-slate-500">
        “Promising” requires the Fixed baseline to have profit factor ≥ 1.20 and a positive average result.
        This is historical research status, not authorization to trade.
      </div>
    </section>
  );
}
