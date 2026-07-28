import React from 'react';
import type { ShadowState } from '../types';
import { Activity, AlertCircle, CheckCircle2, Zap } from 'lucide-react';

interface ShadowTradingPanelProps {
  shadowState: ShadowState;
}

export const ShadowTradingPanel: React.FC<ShadowTradingPanelProps> = ({ shadowState }) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      {/* Active Shadow Execution Intent */}
      <div className="lg:col-span-2 terminal-panel p-6 bg-white border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between mb-4 border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-600" />
            <h2 className="text-base font-bold text-slate-900 font-sans">Forward Shadow Trading Execution Monitor</h2>
          </div>
          <span className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            Session: {shadowState.currentSession}
          </span>
        </div>

        {shadowState.activeIntent ? (
          <div className="p-4 rounded-lg bg-emerald-50/60 border border-emerald-200 text-emerald-950 space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between font-sans">
              <span className="font-bold text-emerald-900 text-sm">Active Forward Intent Detected</span>
              <span className="px-2 py-0.5 rounded text-xs font-bold uppercase bg-emerald-100 text-emerald-800">
                {shadowState.activeIntent.side} {shadowState.activeIntent.symbol}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <div>
                <span className="text-slate-600 block text-[11px]">Entry Price</span>
                <strong className="text-slate-900 text-sm">${shadowState.activeIntent.entryPrice.toFixed(2)}</strong>
              </div>
              <div>
                <span className="text-slate-600 block text-[11px]">Stop Loss</span>
                <strong className="text-rose-700 text-sm">${shadowState.activeIntent.stopPrice.toFixed(2)}</strong>
              </div>
              <div>
                <span className="text-slate-600 block text-[11px]">Take Profit</span>
                <strong className="text-emerald-700 text-sm">${shadowState.activeIntent.targetPrice.toFixed(2)}</strong>
              </div>
              <div>
                <span className="text-slate-600 block text-[11px]">Unrealized PnL</span>
                <strong className="text-emerald-700 text-sm">+${shadowState.activeIntent.unrealizedPnl.toFixed(2)}</strong>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-500 font-sans text-xs bg-slate-50 rounded-lg border border-slate-200">
            No active positions in current session. Scanning for valid Supply/Demand setups...
          </div>
        )}
      </div>

      {/* Decision Log Column */}
      <div className="terminal-panel p-5 bg-white border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2 mb-3 border-b border-slate-200 pb-2">
          <Activity className="w-4 h-4 text-indigo-600" />
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Live Decision Audit Log</h3>
        </div>

        <div className="space-y-3 font-sans text-xs">
          {shadowState.recentDecisions.map((dec, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-slate-500">
                  {new Date(dec.timestamp).toISOString().substring(11, 16)} UTC
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 ${
                    dec.decision === 'signal_accepted'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {dec.decision === 'signal_accepted' ? (
                    <>
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" /> ACCEPTED
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3 h-3 text-slate-500" /> REJECTED
                    </>
                  )}
                </span>
              </div>
              <p className="text-slate-700 text-xs font-medium">{dec.reason}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
