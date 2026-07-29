import React, { useEffect, useRef } from 'react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, Time } from 'lightweight-charts';

/**
 * Equity curve drawn strictly from the producer's recorded performance points.
 *
 * Nothing here is derived or simulated. The visualization contract already
 * computes `equity` and `peak_equity` per trade, so the dashboard's only job is
 * to plot them. An earlier version of this component synthesised a second
 * "Fixed 0.15% baseline" series as `netPnl * 0.75` while it was fed mock data.
 * That number corresponded to no backtest, and once this component started
 * rendering real runs it was presenting an invention as recorded output. It is
 * removed rather than parameterised.
 */

export interface EquityPoint {
  timestamp: string;
  equity: number;
  peak_equity?: number;
}

interface EquityChartProps {
  points: EquityPoint[];
  /** Names the sizing variant actually plotted, e.g. "Fixed 0.15%" or "RRMS". */
  variantLabel: string;
}

const toEpochSeconds = (timestamp: string): Time =>
  Math.floor(new Date(timestamp).getTime() / 1000) as Time;

const money = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);

export const EquityChart: React.FC<EquityChartProps> = ({ points, variantLabel }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || points.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: { background: { color: '#ffffff' }, textColor: '#475569', fontSize: 12 },
      grid: { vertLines: { color: '#f1f5f9' }, horzLines: { color: '#f1f5f9' } },
      rightPriceScale: { borderColor: '#e2e8f0', scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: '#e2e8f0', timeVisible: false, secondsVisible: false },
      handleScroll: { mouseWheel: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true },
    });
    chartRef.current = chart;

    const equitySeries = chart.addSeries(LineSeries, {
      color: '#4f46e5',
      lineWidth: 2,
      title: variantLabel,
    });
    equitySeries.setData(
      points.map((point) => ({ time: toEpochSeconds(point.timestamp), value: point.equity })),
    );

    const hasPeak = points.every((point) => typeof point.peak_equity === 'number');
    if (hasPeak) {
      const peakSeries = chart.addSeries(LineSeries, {
        color: '#94a3b8',
        lineWidth: 1,
        lineStyle: 2,
        title: 'Peak equity',
      });
      peakSeries.setData(
        points.map((point) => ({
          time: toEpochSeconds(point.timestamp),
          value: point.peak_equity as number,
        })),
      );
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (!chartContainerRef.current) return;
      chart.applyOptions({
        width: chartContainerRef.current.clientWidth,
        height: chartContainerRef.current.clientHeight,
      });
    };
    handleResize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [points, variantLabel]);

  const startingEquity = points[0]?.equity;

  return (
    <div className="terminal-panel mb-6 border border-slate-200 bg-white p-4 shadow-xs">
      <div className="mb-3 flex items-center justify-between border-b border-slate-200 pb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-800">
          Equity curve{startingEquity === undefined ? '' : ` (from ${money(startingEquity)})`}
        </h3>
        <div className="flex items-center gap-4 text-xs font-medium">
          <div className="flex items-center gap-1.5">
            <span className="h-1 w-3 rounded bg-indigo-600" />
            <span className="font-semibold text-indigo-900">{variantLabel}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-0.5 w-3 bg-slate-400" />
            <span className="text-slate-600">Peak equity</span>
          </div>
        </div>
      </div>

      <div className="relative h-[320px] w-full overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div ref={chartContainerRef} className="h-full w-full" />
      </div>
    </div>
  );
};
