import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
} from 'lightweight-charts';
import type {
  IChartApi,
  CandlestickData,
  LineData,
  Time,
} from 'lightweight-charts';
import type { Bar, Timeframe, Trade } from '../types';
import { Eye, EyeOff, Maximize2 } from 'lucide-react';

interface CandlestickChartProps {
  bars: Bar[];
  trades: Trade[];
  focusedTrade?: Trade | null;
  selectedTimeframe: Timeframe;
  onSelectTimeframe: (tf: Timeframe) => void;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  bars,
  trades,
  focusedTrade,
  selectedTimeframe,
  onSelectTimeframe,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Toggle states for indicators
  const [showJaw, setShowJaw] = useState(true);
  const [showTeeth, setShowTeeth] = useState(true);
  const [showLips, setShowLips] = useState(true);
  const [useHeikinAshi, setUseHeikinAshi] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 1. Initialize Chart for Light Theme
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#475569',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#f1f5f9' },
        horzLines: { color: '#f1f5f9' },
      },
      crosshair: {
        mode: 1, // Magnet mode
        vertLine: { color: '#4f46e5', width: 1, style: 3 },
        horzLine: { color: '#4f46e5', width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    chartRef.current = chart;

    // 2. Add Candlestick Series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#059669',
      downColor: '#dc2626',
      borderUpColor: '#059669',
      borderDownColor: '#dc2626',
      wickUpColor: '#059669',
      wickDownColor: '#dc2626',
    });

    // 3. Add Alligator Line Series
    const jawSeries = chart.addSeries(LineSeries, {
      color: '#2563eb', // Blue
      lineWidth: 2,
      title: 'Jaw (13)',
    });

    const teethSeries = chart.addSeries(LineSeries, {
      color: '#db2777', // Pink/Red
      lineWidth: 2,
      title: 'Teeth (8)',
    });

    const lipsSeries = chart.addSeries(LineSeries, {
      color: '#059669', // Green
      lineWidth: 2,
      title: 'Lips (5)',
    });

    // 4. Load Candle & Indicator Data
    const candleData: CandlestickData[] = [];
    const jawData: LineData[] = [];
    const teethData: LineData[] = [];
    const lipsData: LineData[] = [];

    bars.forEach((b) => {
      const time = b.time as Time;

      const open = useHeikinAshi && b.haOpen !== undefined ? b.haOpen : b.open;
      const high = useHeikinAshi && b.haHigh !== undefined ? b.haHigh : b.high;
      const low = useHeikinAshi && b.haLow !== undefined ? b.haLow : b.low;
      const close = useHeikinAshi && b.haClose !== undefined ? b.haClose : b.close;

      candleData.push({ time, open, high, low, close });

      if (b.jaw !== undefined) jawData.push({ time, value: b.jaw });
      if (b.teeth !== undefined) teethData.push({ time, value: b.teeth });
      if (b.lips !== undefined) lipsData.push({ time, value: b.lips });
    });

    candleSeries.setData(candleData);
    if (showJaw) jawSeries.setData(jawData);
    if (showTeeth) teethSeries.setData(teethData);
    if (showLips) lipsSeries.setData(lipsData);

    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    chart.timeScale().fitContent();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [bars, trades, showJaw, showTeeth, showLips, useHeikinAshi]);

  // Handle Focus on trade selection
  useEffect(() => {
    if (focusedTrade && chartRef.current) {
      const entryTime = Math.floor(new Date(focusedTrade.entryTimestamp).getTime() / 1000);
      const exitTime = Math.floor(new Date(focusedTrade.exitTimestamp).getTime() / 1000);

      const buffer = 3600 * 12;
      chartRef.current.timeScale().setVisibleRange({
        from: (entryTime - buffer) as Time,
        to: (exitTime + buffer) as Time,
      });
    }
  }, [focusedTrade]);

  return (
    <div className="terminal-panel p-4 mb-6 flex flex-col gap-3 bg-white border border-slate-200 shadow-xs">
      {/* Chart Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
        {/* Timeframe Selector */}
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-slate-600 mr-1">Timeframe:</span>
          {(['15m', '1h', '4h'] as Timeframe[]).map((tf) => (
            <button
              key={tf}
              onClick={() => onSelectTimeframe(tf)}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
                selectedTimeframe === tf
                  ? 'bg-indigo-600 text-white font-bold'
                  : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              {tf}
            </button>
          ))}
          <button
            onClick={() => setUseHeikinAshi(!useHeikinAshi)}
            className={`px-2.5 py-1 rounded text-xs font-semibold ml-2 transition-all cursor-pointer ${
              useHeikinAshi
                ? 'bg-indigo-600 text-white font-bold'
                : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
            }`}
          >
            Heikin Ashi
          </button>
        </div>

        {/* Alligator Indicator Layer Toggles */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Alligator:</span>
          <button
            onClick={() => setShowJaw(!showJaw)}
            className={`px-2.5 py-1 rounded text-xs font-medium gap-1.5 flex items-center cursor-pointer transition-all ${
              showJaw ? 'border border-blue-300 text-blue-700 bg-blue-50 font-semibold' : 'bg-white text-slate-400 border border-slate-200'
            }`}
          >
            {showJaw ? <Eye className="w-3.5 h-3.5 text-blue-600" /> : <EyeOff className="w-3.5 h-3.5 text-slate-400" />}
            Jaw (13)
          </button>
          <button
            onClick={() => setShowTeeth(!showTeeth)}
            className={`px-2.5 py-1 rounded text-xs font-medium gap-1.5 flex items-center cursor-pointer transition-all ${
              showTeeth ? 'border border-pink-300 text-pink-700 bg-pink-50 font-semibold' : 'bg-white text-slate-400 border border-slate-200'
            }`}
          >
            {showTeeth ? <Eye className="w-3.5 h-3.5 text-pink-600" /> : <EyeOff className="w-3.5 h-3.5 text-slate-400" />}
            Teeth (8)
          </button>
          <button
            onClick={() => setShowLips(!showLips)}
            className={`px-2.5 py-1 rounded text-xs font-medium gap-1.5 flex items-center cursor-pointer transition-all ${
              showLips ? 'border border-emerald-300 text-emerald-700 bg-emerald-50 font-semibold' : 'bg-white text-slate-400 border border-slate-200'
            }`}
          >
            {showLips ? <Eye className="w-3.5 h-3.5 text-emerald-600" /> : <EyeOff className="w-3.5 h-3.5 text-slate-400" />}
            Lips (5)
          </button>
        </div>

        {/* Zoom Reset */}
        <button
          onClick={() => chartRef.current?.timeScale().fitContent()}
          className="px-2.5 py-1 rounded text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 flex items-center gap-1 cursor-pointer transition-all"
          title="Reset chart view zoom"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          Reset Zoom
        </button>
      </div>

      {/* Chart Canvas Container */}
      <div className="relative w-full h-[480px] rounded-lg overflow-hidden border border-slate-200 bg-white">
        <div ref={chartContainerRef} className="w-full h-full" />

        {/* Focused Trade Overlay Card */}
        {focusedTrade && (
          <div className="absolute top-3 left-3 p-3 max-w-xs border border-indigo-200 bg-white shadow-md rounded-lg text-xs font-sans">
            <div className="flex items-center justify-between font-bold text-indigo-900 mb-1">
              <span>Trade #{focusedTrade.number} Focused</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${focusedTrade.netPnl >= 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                {focusedTrade.netPnl >= 0 ? 'WIN' : 'LOSS'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-slate-700">
              <div>Entry: <span className="font-semibold text-slate-900">${focusedTrade.entryPrice}</span></div>
              <div>Exit: <span className="font-semibold text-slate-900">${focusedTrade.exitPrice}</span></div>
              <div>Stop: <span className="text-rose-600 font-semibold">${focusedTrade.stopPrice}</span></div>
              <div>Target: <span className="text-emerald-600 font-semibold">${focusedTrade.targetPrice}</span></div>
              <div className="col-span-2 mt-1 pt-1 border-t border-slate-200 flex justify-between">
                <span>Net PnL:</span>
                <span className={`font-bold font-mono ${focusedTrade.netPnl >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                  ${focusedTrade.netPnl.toFixed(2)} ({focusedTrade.resultR.toFixed(2)}R)
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
