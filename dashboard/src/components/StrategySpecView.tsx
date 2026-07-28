import React from 'react';
import type { StrategySpec } from '../types';
import { BookOpen, FileCode, Shield } from 'lucide-react';

interface StrategySpecViewProps {
  spec: StrategySpec;
}

export const StrategySpecView: React.FC<StrategySpecViewProps> = ({ spec }) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      {/* Main Rules & Documentation Panel */}
      <div className="lg:col-span-2 terminal-panel p-6 bg-white border border-slate-200 shadow-xs">
        <div className="flex items-center gap-2 mb-4 border-b border-slate-200 pb-3">
          <BookOpen className="w-5 h-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-900 font-sans">{spec.title}</h2>
        </div>

        <div className="prose prose-slate max-w-none text-slate-800 text-sm leading-relaxed space-y-4">
          {spec.markdownContent.split('\n\n').map((paragraph, idx) => {
            if (paragraph.startsWith('# ')) {
              return (
                <h1 key={idx} className="text-xl font-bold text-slate-900 border-b border-slate-200 pb-2 mt-4">
                  {paragraph.replace('# ', '')}
                </h1>
              );
            }
            if (paragraph.startsWith('## ')) {
              return (
                <h2 key={idx} className="text-base font-semibold text-indigo-900 mt-4 mb-2">
                  {paragraph.replace('## ', '')}
                </h2>
              );
            }
            if (paragraph.startsWith('- ')) {
              return (
                <ul key={idx} className="list-disc list-inside space-y-1 text-slate-700 font-sans">
                  {paragraph.split('\n').map((item, i) => (
                    <li key={i}>{item.replace('- ', '')}</li>
                  ))}
                </ul>
              );
            }
            return (
              <p key={idx} className="text-slate-700 font-sans">
                {paragraph}
              </p>
            );
          })}
        </div>
      </div>

      {/* Indicator Matrix & Risk Policy Side Column */}
      <div className="space-y-6">
        {/* Indicator Definition Matrix */}
        <div className="terminal-panel p-5 bg-white border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-200 pb-2">
            <FileCode className="w-4 h-4 text-sky-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Indicator Rule Matrix</h3>
          </div>

          <div className="space-y-2.5">
            {spec.indicatorRules.map((rule, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                <div className="font-semibold text-slate-900 mb-1">{rule.name}</div>
                <div className="text-slate-600 font-sans">{rule.rule}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk & Position Sizing Policy */}
        <div className="terminal-panel p-5 bg-white border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 mb-3 border-b border-slate-200 pb-2">
            <Shield className="w-4 h-4 text-emerald-600" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Risk & Position Sizing Policy</h3>
          </div>

          <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 font-sans leading-relaxed">
            {spec.riskPolicy}
          </div>
        </div>
      </div>
    </div>
  );
};
