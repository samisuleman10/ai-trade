import React from 'react';
import type { VisualRender } from '../types';
import { Image as ImageIcon } from 'lucide-react';

interface VisualGalleryProps {
  visuals: VisualRender[];
}

export const VisualGallery: React.FC<VisualGalleryProps> = ({ visuals }) => {
  return (
    <div className="space-y-6 mb-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-indigo-600" />
            Stored Visual Renders Gallery
          </h2>
          <p className="text-xs text-slate-500 font-sans">
            SVG charts, zone diagnostics, and trade review renders saved by the strategy backtest engine.
          </p>
        </div>
        <span className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
          {visuals.length} Visual Artifacts
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {visuals.map((visual) => (
          <div key={visual.id} className="terminal-panel p-4 bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-100 text-slate-700 border border-slate-200">
                  {visual.category}
                </span>
                <span className="text-[10px] font-mono text-slate-400">ID: {visual.id}</span>
              </div>
              <h3 className="text-xs font-bold text-slate-900 mb-1">{visual.title}</h3>
              <p className="text-xs text-slate-600 font-sans mb-3 line-clamp-2">{visual.description}</p>
            </div>

            <div
              className="w-full rounded-lg overflow-hidden border border-slate-200 bg-slate-50 p-2"
              dangerouslySetInnerHTML={{ __html: visual.svgContent }}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
