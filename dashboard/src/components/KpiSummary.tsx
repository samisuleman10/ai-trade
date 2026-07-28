import React from 'react';
import { ArrowDownRight, ArrowUpRight, DollarSign, Percent, Scale, ShieldAlert, TrendingUp } from 'lucide-react';
import type { StrategySummary } from '../types';

interface KpiSummaryProps {
  summary: StrategySummary;
  useRrms: boolean;
  onToggleRrms: (value: boolean) => void;
}

export const KpiSummary: React.FC<KpiSummaryProps> = ({ summary, useRrms, onToggleRrms }) => {
  const netPnl = useRrms ? summary.netPnlRrms : summary.netPnlFixed;
  const profitFactor = useRrms ? summary.profitFactorRrms : summary.profitFactorFixed;
  const maxDrawdown = useRrms ? summary.maxDrawdownRrms : summary.maxDrawdownFixed;
  const endingEquity = useRrms ? summary.endingEquityRrms : summary.endingEquityFixed;
  const pnlPercent = ((netPnl / summary.startingEquity) * 100).toFixed(2);
  const isProfitable = netPnl >= 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3.5 mb-6">
      {/* 1. Net PnL Card */}
      <div className="terminal-card p-4 relative overflow-hidden bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Net Strategy PnL</span>
          <button
            onClick={() => onToggleRrms(!useRrms)}
            className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-indigo-100 text-indigo-800 hover:bg-indigo-200 transition-all border border-indigo-300 cursor-pointer"
          >
            {useRrms ? 'RRMS Active' : 'Fixed Risk'}
          </button>
        </div>
        <div className={`text-2xl font-bold font-mono tracking-tight ${isProfitable ? 'text-emerald-700' : 'text-rose-700'}`}>
          ${netPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="flex items-center gap-1.5 mt-1.5 text-xs font-semibold">
          {isProfitable ? (
            <span className="text-emerald-700 flex items-center font-semibold">
              <ArrowUpRight className="w-4 h-4" /> +{pnlPercent}%
            </span>
          ) : (
            <span className="text-rose-700 flex items-center font-semibold">
              <ArrowDownRight className="w-4 h-4" /> {pnlPercent}%
            </span>
          )}
          <span className="text-slate-600 font-mono font-normal">from $100k capital</span>
        </div>
      </div>

      {/* 2. Win Rate Card */}
      <div className="terminal-card p-4 bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Win Rate</span>
          <Percent className="w-4 h-4 text-emerald-600" />
        </div>
        <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight">
          {(summary.winRate * 100).toFixed(1)}%
        </div>
        <div className="text-xs text-slate-700 mt-1.5 font-medium flex items-center justify-between">
          <span><strong className="text-emerald-700 font-mono font-semibold">{summary.wins} W</strong> / <strong className="text-rose-700 font-mono font-semibold">{summary.losses} L</strong></span>
          <span className="text-slate-600 font-mono">{summary.totalTrades} Trades</span>
        </div>
      </div>

      {/* 3. Profit Factor Card */}
      <div className="terminal-card p-4 bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Profit Factor</span>
          <TrendingUp className="w-4 h-4 text-indigo-600" />
        </div>
        <div className={`text-2xl font-bold font-mono tracking-tight ${profitFactor >= 1.0 ? 'text-emerald-700' : 'text-amber-700'}`}>
          {profitFactor.toFixed(3)}
        </div>
        <div className="text-xs text-slate-700 mt-1.5 font-medium">
          {profitFactor >= 1.0 ? 'Positive Expectancy' : 'Below Baseline'}
        </div>
      </div>

      {/* 4. Max Drawdown Card */}
      <div className="terminal-card p-4 bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Max Drawdown</span>
          <ShieldAlert className="w-4 h-4 text-rose-600" />
        </div>
        <div className="text-2xl font-bold font-mono text-rose-700 tracking-tight">
          -${maxDrawdown.toFixed(2)}
        </div>
        <div className="text-xs text-slate-700 mt-1.5 font-mono">
          {((maxDrawdown / summary.startingEquity) * 100).toFixed(2)}% Peak Depth
        </div>
      </div>

      {/* 5. Average R Card */}
      <div className="terminal-card p-4 bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Average R</span>
          <Scale className="w-4 h-4 text-sky-700" />
        </div>
        <div className={`text-2xl font-bold font-mono tracking-tight ${summary.avgR >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
          {summary.avgR > 0 ? `+${summary.avgR.toFixed(3)}R` : `${summary.avgR.toFixed(3)}R`}
        </div>
        <div className="text-xs text-slate-700 mt-1.5 font-medium">Risk-to-Reward Ratio</div>
      </div>

      {/* 6. Ending Equity Card */}
      <div className="terminal-card p-4 bg-[#f8fafc] border border-slate-300 shadow-xs">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-600 mb-1.5 uppercase tracking-wider">
          <span>Ending Equity</span>
          <DollarSign className="w-4 h-4 text-emerald-600" />
        </div>
        <div className="text-2xl font-bold font-mono text-slate-900 tracking-tight">
          ${endingEquity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="text-xs text-slate-700 mt-1.5 font-medium">Simulated Account Balance</div>
      </div>
    </div>
  );
};
