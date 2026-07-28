import { useEffect, useRef } from 'react';
import { CandlestickSeries, LineSeries, createChart, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, SeriesMarker, Time } from 'lightweight-charts';
import type { FixtureBar } from '../strategy04Fixture';
import { toChartBars } from '../strategy04Fixture';

export interface TradeChartHandles {
  chart: IChartApi;
  candles: ISeriesApi<'Candlestick'>;
  span: Time[];
  drawLevel: (price: number, color: string, dotted: boolean, title: string) => void;
  setMarkers: (markers: SeriesMarker<Time>[]) => void;
}

const CHART_OPTIONS = {
  layout: { background: { color: '#ffffff' }, textColor: '#64748b', fontSize: 11 },
  grid: { vertLines: { color: '#eef2f7' }, horzLines: { color: '#eef2f7' } },
  rightPriceScale: { borderColor: '#dbe3ee', scaleMargins: { top: 0.12, bottom: 0.12 } },
  timeScale: { borderColor: '#dbe3ee', timeVisible: true, secondsVisible: false },
};

const CANDLE_OPTIONS = {
  upColor: '#0f9f74',
  downColor: '#e24c63',
  borderUpColor: '#0f9f74',
  borderDownColor: '#e24c63',
  wickUpColor: '#0f9f74',
  wickDownColor: '#e24c63',
};

/**
 * Build a candlestick chart from fixture bars and hand the caller the pieces
 * it needs to draw price levels and markers on top.
 */
export function useTradeChart(
  bars: FixtureBar[],
  lineWidth: 1 | 2,
  decorate: (handles: TradeChartHandles) => void,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const decorateRef = useRef(decorate);
  decorateRef.current = decorate;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, CHART_OPTIONS);
    const chartBars = toChartBars(bars);
    const candles = chart.addSeries(CandlestickSeries, CANDLE_OPTIONS);
    candles.setData(
      chartBars.map((bar) => ({
        time: bar.time as Time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );

    const span = chartBars.map((bar) => bar.time as Time);
    const drawLevel = (price: number, color: string, dotted: boolean, title: string) => {
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth,
        lineStyle: dotted ? 2 : 0,
        priceLineVisible: false,
        lastValueVisible: true,
        title,
      });
      series.setData(span.map((time) => ({ time, value: price })));
    };

    const markersPlugin = createSeriesMarkers(candles, []);

    decorateRef.current({
      chart,
      candles,
      span,
      drawLevel,
      setMarkers: (markers) => markersPlugin.setMarkers(markers),
    });

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
  }, [bars, lineWidth]);

  return containerRef;
}
