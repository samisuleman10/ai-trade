import type { AuditedTrade } from '../strategy04Fixture';
import { failedChecks } from '../strategy04Fixture';

interface Props {
  trades: AuditedTrade[];
  selectedTradeId: string | null;
  onSelect: (tradeId: string) => void;
}

const shortTime = (timestamp: string) => timestamp.replace('T', ' ').replace(':00Z', '');

export function AuditedTradeList({ trades, selectedTradeId, onSelect }: Props) {
  const failing = trades.filter((trade) => !trade.audit.passed).length;

  return (
    <section className="s4-panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div>
          <div className="s4-eyebrow">Trade ledger</div>
          <h2 className="mt-1 text-base font-semibold text-slate-950">
            {trades.length} trades
          </h2>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">
            {trades.length - failing} checks passed
          </span>
          {failing > 0 && (
            <span className="rounded bg-rose-50 px-2 py-1 text-rose-700">
              {failing} need review
            </span>
          )}
        </div>
      </div>
      <div className="max-h-[420px] overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">#</th>
              <th className="px-4 py-2 font-medium">Entry</th>
              <th className="px-4 py-2 font-medium">Side</th>
              <th className="px-4 py-2 font-medium text-right">R</th>
              <th className="px-4 py-2 font-medium">Outcome</th>
              <th className="px-4 py-2 font-medium">Audit</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => {
              const failed = failedChecks(trade);
              const isSelected = trade.trade_id === selectedTradeId;
              return (
                <tr
                  key={trade.trade_id}
                  onClick={() => onSelect(trade.trade_id)}
                  className={`cursor-pointer border-t border-slate-100 ${
                    isSelected ? 'bg-sky-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-slate-500">{trade.ordinal}</td>
                  <td className="px-4 py-2 font-mono">{shortTime(trade.entry_timestamp)}</td>
                  <td className="px-4 py-2 capitalize">{trade.side}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {trade.result_r >= 0 ? '+' : ''}
                    {trade.result_r.toFixed(2)}
                  </td>
                  <td
                    className={`px-4 py-2 ${
                      trade.exit_reason === 'target' ? 'text-emerald-700' : 'text-rose-700'
                    }`}
                  >
                    {trade.exit_reason}
                  </td>
                  <td className="px-4 py-2">
                    {failed.length === 0 ? (
                      <span className="text-emerald-700">pass</span>
                    ) : (
                      <span className="text-rose-700" title={failed.map((c) => c.check_id).join(', ')}>
                        {failed.map((c) => c.check_id).join(', ')}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
