import React from 'react';
import { Activity, RefreshCw } from 'lucide-react';

interface HeaderProps {
  strategyName: string;
  versionName: string;
  selectedAsset: string;
  riskPolicy?: string;
  isBackendConnected: boolean;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  strategyName,
  versionName,
  selectedAsset,
  riskPolicy = '0.15% Risk / Trade',
  isBackendConnected,
  onRefresh,
  isRefreshing,
}) => {
  return (
    <header className="terminal-panel px-6 py-3.5 mb-4 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4 bg-[#f8fafc] border border-slate-200 shadow-xs">
      {/* Left: Brand Identity */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
          <Activity className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold tracking-tight text-slate-900 font-mono">AI TRADE</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase tracking-wider">
              Studio
            </span>
          </div>
          <p className="text-xs text-slate-500 font-normal">Algorithmic Backtesting & Strategy Hub</p>
        </div>
      </div>

      {/* Center: Strategy Context Text Summary */}
      <div className="flex items-center gap-4 flex-wrap text-xs font-mono bg-[#f1f5f9] px-4 py-2 rounded-lg border border-slate-200 text-slate-800">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-600" />
          <span className="text-slate-500 font-sans">Active:</span>
          <strong className="text-slate-900 font-semibold">{strategyName}</strong>
          <span className="text-indigo-700 font-medium">({versionName})</span>
        </div>
        <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
          <span className="text-slate-500 font-sans">Asset:</span>
          <strong className="text-sky-800 font-semibold">{selectedAsset}</strong>
        </div>
        <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
          <span className="text-slate-500 font-sans">Coverage:</span>
          <span className="text-slate-800">2-Year RTH</span>
        </div>
        <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
          <span className="text-slate-500 font-sans">Risk:</span>
          <strong className="text-indigo-800 font-semibold">{riskPolicy}</strong>
        </div>
        <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
          <span className="text-slate-500 font-sans">Engine:</span>
          <strong className="text-emerald-800 font-semibold">Deterministic Replay</strong>
        </div>
      </div>

      {/* Far Right: Connection Status & Refresh */}
      <div className="flex items-center gap-3">
        <div
          className={`flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg border ${
            isBackendConnected
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-amber-50 text-amber-800 border-amber-200'
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${isBackendConnected ? 'bg-emerald-600' : 'bg-amber-600'}`} />
          {isBackendConnected ? 'API Live' : 'Offline Mode'}
        </div>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-[#f1f5f9] border border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-200 transition-all cursor-pointer"
          title="Refresh strategy outputs"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-indigo-600' : ''}`} />
        </button>
      </div>
    </header>
  );
};
