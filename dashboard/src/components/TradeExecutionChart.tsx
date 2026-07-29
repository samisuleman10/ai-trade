import type { SeriesMarker, Time } from 'lightweight-charts';
import type { AuditedTrade } from '../strategy04Audit';
import { toEpochSeconds } from '../strategy04Audit';
import { useTradeChart } from './useTradeChart';

interface Props {
  trade: AuditedTrade;
}

// Bars of breathing room either side of the trade in the default view. The
// bar window is deliberately wider than the trade so you can pan into the
// approach, but opening zoomed all the way out makes the candles unreadable.
const FOCUS_PADDING_BARS = 6;

export function TradeExecutionChart({ trade }: Props) {
  const containerRef = useTradeChart(trade.bars.fifteen_minute, 2, ({ chart, span, drawLevel, setMarkers }) => {
    drawLevel(trade.target_price, '#1d9e75', true, `target ${trade.target_price.toFixed(2)}`);
    drawLevel(trade.entry_price, '#378add', false, `entry ${trade.entry_price.toFixed(2)}`);
    drawLevel(trade.stop_price, '#e24b4a', true, `stop ${trade.stop_price.toFixed(2)}`);

    const markers: SeriesMarker<Time>[] = [
      {
        // Trigger and entry are adjacent bars. Placing them on opposite sides
        // of the candle keeps their labels from overlapping into each other.
        time: toEpochSeconds(trade.trigger_timestamp) as Time,
        position: 'aboveBar',
        color: '#639922',
        shape: 'arrowDown',
        text: 'trigger',
      },
      {
        time: toEpochSeconds(trade.entry_timestamp) as Time,
        position: 'belowBar',
        color: '#378add',
        shape: 'arrowUp',
        text: 'entry',
      },
      {
        time: toEpochSeconds(trade.exit_timestamp) as Time,
        position: 'aboveBar',
        color: trade.exit_reason === 'target' ? '#1d9e75' : '#e24b4a',
        shape: 'arrowDown',
        text: `${trade.exit_reason} ${trade.result_r >= 0 ? '+' : ''}${trade.result_r.toFixed(2)}R`,
      },
    ];
    setMarkers(markers);

    const at = (timestamp: string) => {
      const target = toEpochSeconds(timestamp);
      const index = span.findIndex((time) => (time as number) >= target);
      return index === -1 ? span.length - 1 : index;
    };
    const first = Math.max(0, at(trade.trigger_timestamp) - FOCUS_PADDING_BARS);
    const last = Math.min(span.length - 1, at(trade.exit_timestamp) + FOCUS_PADDING_BARS);
    if (last > first) {
      chart.timeScale().setVisibleRange({ from: span[first], to: span[last] });
    }
  });

  return (
    <section className="s4-panel overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="s4-eyebrow">15 minutes — the execution</div>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          What happened to trade {trade.ordinal}
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Entry {trade.entry_price.toFixed(2)} · stop {trade.stop_price.toFixed(2)} · target{' '}
          {trade.target_price.toFixed(2)} · exited at {trade.exit_price.toFixed(2)} by {trade.exit_reason}
        </p>
      </div>
      <div ref={containerRef} className="h-[460px] w-full bg-white" />
    </section>
  );
}
