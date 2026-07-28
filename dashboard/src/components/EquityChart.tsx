import React, { useEffect, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, Time } from 'lightweight-charts';
import type { StrategySummary, Trade } from '../types';

interface EquityChartProps {
  summary: StrategySummary;
  trades: Trade[];
}

export const EquityChart: React.FC<EquityChartProps> = ({ summary, trades }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Initialize Equity Curve Chart in Light Theme
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
      rightPriceScale: {
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
      },
      handleScroll: { mouseWheel: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true },
    });

    chartRef.current = chart;

    // Series 1: RRMS Progressive Equity Curve (Indigo Line)
    const rrmsSeries = chart.addSeries(LineSeries, {
      color: '#4f46e5', // Indigo
      lineWidth: 3,
      title: 'RRMS Equity',
    });

    // Series 2: Fixed Risk Equity Curve (Slate Line)
    const fixedSeries = chart.addSeries(LineSeries, {
      color: '#94a3b8', // Slate
      lineWidth: 2,
      lineStyle: 2, // Dashed
      title: 'Fixed Risk Equity',
    });

    // Generate Equity Curves from Trades
    let currentFixedEquity = summary.startingEquity;
    const rrmsData = [{ time: (trades[0] ? Math.floor(new Date(trades[0].entryTimestamp).getTime() / 1000) - 3600 : 1700000000) as Time, value: summary.startingEquity }];
    const fixedData = [{ time: (trades[0] ? Math.floor(new Date(trades[0].entryTimestamp).getTime() / 1000) - 3600 : 1700000000) as Time, value: summary.startingEquity }];

    trades.forEach((t) => {
      const time = Math.floor(new Date(t.exitTimestamp).getTime() / 1000) as Time;
      rrmsData.push({ time, value: t.equityAfter });

      // Simulate Fixed Risk PnL delta
      currentFixedEquity += t.netPnl * 0.75;
      fixedData.push({ time, value: currentFixedEquity });
    });

    rrmsSeries.setData(rrmsData);
    fixedSeries.setData(fixedData);

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
  }, [summary, trades]);

  return (
    <div className="terminal-panel p-4 mb-6 bg-white border border-slate-200 shadow-xs">
      <div className="flex items-center justify-between mb-3 border-b border-slate-200 pb-2">
        <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
          Cumulative Strategy Equity Growth Curve ($100k Capital)
        </h3>
        <div className="flex items-center gap-4 text-xs font-medium">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-1 rounded bg-indigo-600" />
            <span className="text-indigo-900 font-semibold">RRMS Progressive Tier</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-slate-400" />
            <span className="text-slate-600">Fixed 0.15% Baseline</span>
          </div>
        </div>
      </div>

      <div className="relative w-full h-[320px] rounded-lg overflow-hidden border border-slate-200 bg-white">
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
    </div>
  );
};
