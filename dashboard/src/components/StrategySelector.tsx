import React from 'react';
import type { StrategyDefinition, StrategyId } from '../types';
import { ChevronRight, Database, Layers, Layers2 } from 'lucide-react';

interface StrategySelectorProps {
  strategies: StrategyDefinition[];
  selectedStrategyId: StrategyId;
  onSelectStrategy: (id: StrategyId) => void;
  selectedVersionId: string;
  onSelectVersion: (versionId: string) => void;
  selectedAsset: string;
  onSelectAsset: (asset: string) => void;
}

export const StrategySelector: React.FC<StrategySelectorProps> = ({
  strategies,
  selectedStrategyId,
  onSelectStrategy,
  selectedVersionId,
  onSelectVersion,
  selectedAsset,
  onSelectAsset,
}) => {
  const currentStrategy = strategies.find((s) => s.id === selectedStrategyId) || strategies[0];
  const currentVersionDef = currentStrategy.versions.find((v) => v.id === selectedVersionId) || currentStrategy.versions[0];

  return (
    <div className="space-y-3 mb-6">
      {/* ROW 2: Primary Strategy Selection Row */}
      <div className="terminal-panel p-3.5 bg-[#f8fafc] border border-slate-200 shadow-xs flex items-center justify-between gap-4 overflow-x-auto">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-800 min-w-max">
          <Layers className="w-4 h-4 text-indigo-600" />
          <span>Select Strategy:</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {strategies.map((s) => {
            const isSelected = s.id === selectedStrategyId;
            return (
              <button
                key={s.id}
                onClick={() => onSelectStrategy(s.id)}
                className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-600 text-white shadow-xs border border-indigo-700 font-bold'
                    : 'bg-[#f1f5f9] text-slate-800 hover:bg-slate-200 border border-slate-200'
                }`}
              >
                <span>{s.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ROW 3: Version Iteration (Left) & Target Asset (Right) */}
      <div className="terminal-panel p-3.5 bg-[#f8fafc] border border-slate-200 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Version Iteration (Left) */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs font-mono font-medium text-slate-800">
            <Layers2 className="w-4 h-4 text-indigo-600" />
            <span className="text-slate-500 font-sans">Active Context:</span>
            <span className="text-slate-900 font-bold">{currentStrategy.code}</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-indigo-700 font-sans font-semibold">Version Iteration:</span>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap">
            {currentStrategy.versions.map((v) => {
              const isSelected = v.id === selectedVersionId;
              return (
                <button
                  key={v.id}
                  onClick={() => !v.isPlanned && onSelectVersion(v.id)}
                  disabled={v.isPlanned}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                    isSelected
                      ? 'bg-indigo-50 text-indigo-900 border border-indigo-300 font-semibold shadow-2xs'
                      : v.isPlanned
                      ? 'bg-[#f1f5f9] text-slate-400 border border-slate-200 cursor-not-allowed'
                      : 'bg-[#f1f5f9] text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                  }`}
                >
                  <span>{v.name}</span>
                  {v.isPlanned && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 border border-amber-200 font-sans font-medium">
                      Planned
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Target Asset Switcher (Right) */}
        <div className="flex items-center gap-2 bg-[#f1f5f9] p-1.5 rounded-lg border border-slate-200">
          <Database className="w-3.5 h-3.5 text-sky-700 ml-1" />
          <span className="text-xs font-medium text-slate-600">Target Asset:</span>
          <div className="flex items-center gap-1">
            {currentVersionDef.assets.map((asset) => (
              <button
                key={asset}
                onClick={() => onSelectAsset(asset)}
                className={`px-2.5 py-1 rounded text-xs font-mono font-semibold transition-all cursor-pointer ${
                  selectedAsset === asset
                    ? 'bg-sky-700 text-white shadow-2xs'
                    : 'text-slate-700 hover:text-slate-900 hover:bg-slate-200'
                }`}
              >
                {asset}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
