import { useEffect, useMemo, useRef } from 'react';
import { CandlestickSeries, createChart } from 'lightweight-charts';
import type { CandlestickData, IChartApi, Time } from 'lightweight-charts';
import { Maximize2 } from 'lucide-react';
import type { Bar } from '../types';
import type { Strategy04Timeframe } from '../strategy04Data';

interface Props {
  bars: Bar[];
  timeframe: Strategy04Timeframe;
  onTimeframeChange: (timeframe: Strategy04Timeframe) => void;
}

function aggregateToHourly(bars: Bar[]): Bar[] {
  const groups: Bar[][] = [];
  for (let index = 0; index < bars.length; index += 4) {
    groups.push(bars.slice(index, index + 4));
  }

  return groups
    .filter((group) => group.length > 0)
    .map((group) => ({
      time: group[0].time,
      open: group[0].open,
      high: Math.max(...group.map((bar) => bar.high)),
      low: Math.min(...group.map((bar) => bar.low)),
      close: group[group.length - 1].close,
      volume: group.reduce((sum, bar) => sum + (bar.volume ?? 0), 0),
    }));
}

export function Strategy04PriceChart({ bars, timeframe, onTimeframeChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const visibleBars = useMemo(
    () => (timeframe === '1h' ? aggregateToHourly(bars) : bars),
    [bars, timeframe],
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#64748b',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#eef2f7' },
        horzLines: { color: '#eef2f7' },
      },
      rightPriceScale: {
        borderColor: '#dbe3ee',
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: '#dbe3ee',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: '#64748b', style: 3, width: 1 },
        horzLine: { color: '#64748b', style: 3, width: 1 },
      },
    });

    chartRef.current = chart;
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#0f9f74',
      downColor: '#e24c63',
      borderUpColor: '#0f9f74',
      borderDownColor: '#e24c63',
      wickUpColor: '#0f9f74',
      wickDownColor: '#e24c63',
    });
    const data: CandlestickData[] = visibleBars.map((bar) => ({
      time: bar.time as Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));
    candles.setData(data);
    chart.timeScale().fitContent();

    const resize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    };
    resize();
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      chart.remove();
    };
  }, [visibleBars]);

  return (
    <section className="s4-panel overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="s4-eyebrow">Market context</div>
          <h2 className="mt-1 text-base font-semibold text-slate-950">Price by strategy timeframe</h2>
          <p className="mt-1 text-xs text-slate-500">
            Switch between the 1-hour zone layer and 15-minute execution layer.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="s4-segment" aria-label="Chart timeframe">
            {(['1h', '15m'] as Strategy04Timeframe[]).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={timeframe === value}
                onClick={() => onTimeframeChange(value)}
                className={timeframe === value ? 'is-active' : ''}
              >
                {value === '1h' ? '1H zones' : '15M entries'}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="s4-icon-button"
            aria-label="Reset chart zoom"
            onClick={() => chartRef.current?.timeScale().fitContent()}
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>
      <div ref={containerRef} className="h-[390px] w-full bg-white" />
      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-5 py-2 text-[11px] text-slate-500">
        <span>Preview candles while the versioned candle/zone API contract is connected.</span>
        <span className="font-mono">{visibleBars.length} bars shown</span>
      </div>
    </section>
  );
}
