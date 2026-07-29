import type { SeriesMarker, Time } from 'lightweight-charts';
import type { AuditedTrade } from '../strategy04Fixture';
import { toEpochSeconds } from '../strategy04Fixture';
import { useTradeChart } from './useTradeChart';

interface Props {
  trade: AuditedTrade;
}

export function TradeExecutionChart({ trade }: Props) {
  const containerRef = useTradeChart(trade.bars.fifteen_minute, 2, ({ drawLevel, setMarkers }) => {
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
      <div ref={containerRef} className="h-[320px] w-full bg-white" />
    </section>
  );
}
