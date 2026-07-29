import React, { useState } from 'react';
import type { Trade } from '../types';
import { ArrowUpDown, Focus, Search } from 'lucide-react';

interface TradeTableProps {
  trades: Trade[];
  focusedTradeId?: string;
  onFocusTrade: (trade: Trade) => void;
}

type SortField = 'number' | 'entryTimestamp' | 'netPnl' | 'resultR';

/**
 * A sortable column heading.
 *
 * The control is a real `<button>` rather than a click handler on the `<th>`,
 * so it is reachable by keyboard, and the `<th>` carries `aria-sort` so a
 * screen reader announces the current direction instead of leaving sorting
 * as a purely visual affordance.
 */
const SortableHeader: React.FC<{
  field: SortField;
  label: string;
  activeField: SortField;
  ascending: boolean;
  align?: 'left' | 'right';
  onSort: (field: SortField) => void;
}> = ({ field, label, activeField, ascending, align = 'left', onSort }) => {
  const isActive = activeField === field;
  return (
    <th
      className={`p-3 ${align === 'right' ? 'text-right' : ''}`}
      aria-sort={isActive ? (ascending ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => onSort(field)}
        className={`flex items-center gap-1 uppercase tracking-wider hover:text-slate-900 ${
          align === 'right' ? 'ml-auto justify-end' : ''
        }`}
      >
        {label}
        <ArrowUpDown className="h-3 w-3 text-slate-400" aria-hidden="true" />
      </button>
    </th>
  );
};

export const TradeTable: React.FC<TradeTableProps> = ({ trades, focusedTradeId, onFocusTrade }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sideFilter, setSideFilter] = useState<'all' | 'long' | 'short'>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [sortField, setSortField] = useState<'number' | 'entryTimestamp' | 'netPnl' | 'resultR'>('number');
  const [sortAsc, setSortAsc] = useState(true);

  // Filter trades
  const filteredTrades = trades.filter((t) => {
    const matchesSearch =
      t.number.toString().includes(searchTerm) ||
      t.exitReason.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.entryPrice.toString().includes(searchTerm);

    const matchesSide = sideFilter === 'all' || t.side === sideFilter;
    const matchesOutcome =
      outcomeFilter === 'all' ||
      (outcomeFilter === 'win' && t.netPnl >= 0) ||
      (outcomeFilter === 'loss' && t.netPnl < 0);

    return matchesSearch && matchesSide && matchesOutcome;
  });

  // Sort trades
  const sortedTrades = [...filteredTrades].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];

    if (typeof valA === 'string') valA = (valA as string).toLowerCase();
    if (typeof valB === 'string') valB = (valB as string).toLowerCase();

    if (valA < valB) return sortAsc ? -1 : 1;
    if (valA > valB) return sortAsc ? 1 : -1;
    return 0;
  });

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  return (
    <div className="terminal-panel p-4 bg-white border border-slate-200 shadow-xs">
      {/* Table Controls Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-slate-900">Trade Execution Explorer</h3>
          <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {sortedTrades.length} Trades
          </span>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          {/* Search Input */}
          <div className="relative flex-1 sm:w-48">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" aria-hidden="true" />
            <input
              type="text"
              id="trade-search"
              aria-label="Search trades by date, price or exit reason"
              placeholder="Search date, price, exit..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Side Filter */}
          <select
            aria-label="Filter trades by side"
            value={sideFilter}
            onChange={(e) => setSideFilter(e.target.value as any)}
            className="bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none cursor-pointer"
          >
            <option value="all">All Sides</option>
            <option value="long">Long Only</option>
            <option value="short">Short Only</option>
          </select>

          {/* Outcome Filter */}
          <select
            aria-label="Filter trades by outcome"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value as any)}
            className="bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 text-xs text-slate-700 focus:outline-none cursor-pointer"
          >
            <option value="all">All Outcomes</option>
            <option value="win">Wins Only</option>
            <option value="loss">Losses Only</option>
          </select>
        </div>
      </div>

      {/* Trade Log Data Matrix */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-left text-xs font-mono border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
              <SortableHeader
                field="number"
                label="#"
                activeField={sortField}
                ascending={sortAsc}
                onSort={toggleSort}
              />
              <th className="p-3">Side</th>
              <SortableHeader
                field="entryTimestamp"
                label="Entry Time (UTC)"
                activeField={sortField}
                ascending={sortAsc}
                onSort={toggleSort}
              />
              <th className="p-3 text-right">Qty</th>
              <th className="p-3 text-right">Entry Price</th>
              <th className="p-3 text-right text-rose-600">Stop Loss</th>
              <th className="p-3 text-right text-emerald-600">Target Price</th>
              <th className="p-3 text-right">Exit Price</th>
              <th className="p-3">Exit Reason</th>
              <SortableHeader
                field="netPnl"
                label="Net PnL"
                activeField={sortField}
                ascending={sortAsc}
                align="right"
                onSort={toggleSort}
              />
              <SortableHeader
                field="resultR"
                label="Result R"
                activeField={sortField}
                ascending={sortAsc}
                align="right"
                onSort={toggleSort}
              />
              <th className="p-3 text-center">Focus</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {sortedTrades.length === 0 ? (
              <tr>
                <td colSpan={12} className="p-8 text-center text-slate-500 font-sans">
                  No trades match the selected filter criteria.
                </td>
              </tr>
            ) : (
              sortedTrades.map((t) => {
                const isFocused = t.id === focusedTradeId;
                const isWin = t.netPnl >= 0;

                return (
                  <tr
                    key={t.id}
                    className={`transition-colors hover:bg-slate-50 ${
                      isFocused ? 'bg-indigo-50/70 border-l-4 border-l-indigo-600' : ''
                    }`}
                  >
                    <td className="p-3 font-semibold text-slate-900">#{t.number}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          t.side === 'long'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="p-3 text-slate-600">
                      {t.entryTimestamp ? new Date(t.entryTimestamp).toISOString().replace('T', ' ').substring(0, 16) : '-'}
                    </td>
                    <td className="p-3 text-right text-slate-700">{t.quantity}</td>
                    <td className="p-3 text-right font-semibold text-slate-900">${t.entryPrice.toFixed(2)}</td>
                    <td className="p-3 text-right text-rose-600 font-semibold">${t.stopPrice.toFixed(2)}</td>
                    <td className="p-3 text-right text-emerald-600 font-semibold">${t.targetPrice.toFixed(2)}</td>
                    <td className="p-3 text-right font-semibold text-slate-900">${t.exitPrice.toFixed(2)}</td>
                    <td className="p-3">
                      <span className="capitalize text-slate-700">{t.exitReason}</span>
                    </td>
                    <td className={`p-3 text-right font-bold ${isWin ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {isWin ? '+' : ''}${t.netPnl.toFixed(2)}
                    </td>
                    <td className={`p-3 text-right font-bold ${isWin ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {t.resultR > 0 ? `+${t.resultR.toFixed(2)}R` : `${t.resultR.toFixed(2)}R`}
                    </td>
                    <td className="p-3 text-center">
                      <button
                        type="button"
                        onClick={() => onFocusTrade(t)}
                        className="p-1.5 rounded bg-slate-100 hover:bg-indigo-100 text-slate-600 hover:text-indigo-700 transition-all cursor-pointer"
                        aria-label={`Focus trade ${t.number} on the candlestick chart`}
                        title="Focus trade on candlestick chart"
                      >
                        <Focus className="w-3.5 h-3.5" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
