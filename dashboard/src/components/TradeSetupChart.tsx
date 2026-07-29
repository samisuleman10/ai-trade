import type { SeriesMarker, Time } from 'lightweight-charts';
import type { AuditedTrade } from '../strategy04Fixture';
import { toEpochSeconds } from '../strategy04Fixture';
import { useTradeChart } from './useTradeChart';

interface Props {
  trade: AuditedTrade;
}

// Supply is resistance and only ever produces shorts; demand is support and
// only ever produces longs. Colouring by side means the chart reads the same
// direction as the trade without checking the label.
const SUPPLY_COLOR = '#e24c63';
const DEMAND_COLOR = '#0f9f74';

const zoneColor = (side: string) => (side === 'supply' ? SUPPLY_COLOR : DEMAND_COLOR);

export function TradeSetupChart({ trade }: Props) {
  const containerRef = useTradeChart(trade.bars.one_hour, 1, ({ drawLevel, setMarkers }) => {
    const zone = trade.zones.selected;
    const color = zoneColor(zone.side);
    drawLevel(zone.lower, color, false, `${zone.side} ${zone.lower.toFixed(2)}`);
    drawLevel(zone.upper, color, false, `score ${zone.score}`);
    trade.zones.competing.forEach((competitor) => {
      const competitorColor = zoneColor(competitor.side);
      drawLevel(competitor.lower, competitorColor, true, `#${competitor.zone_id} score ${competitor.score}`);
      drawLevel(competitor.upper, competitorColor, true, '');
    });

    const markers: SeriesMarker<Time>[] = [];
    if (zone.qualified_timestamp) {
      markers.push({
        time: toEpochSeconds(zone.qualified_timestamp) as Time,
        position: 'aboveBar',
        color: '#185fa5',
        shape: 'arrowDown',
        text: 'zone qualified',
      });
    }
    markers.push({
      time: toEpochSeconds(trade.trigger_timestamp) as Time,
      position: 'belowBar',
      color: '#ba7517',
      shape: 'arrowUp',
      text: 'trigger',
    });
    setMarkers(markers);
  });

  return (
    <section className="s4-panel overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="s4-eyebrow">1 hour — the setup</div>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          Why trade {trade.ordinal} was allowed to exist
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          {trade.zones.selected.side} zone {trade.zones.selected.lower.toFixed(2)}–
          {trade.zones.selected.upper.toFixed(2)} · score {trade.zones.selected.score} ·{' '}
          {trade.zones.competing.length} competing zone(s) shown dotted
        </p>
      </div>
      <div ref={containerRef} className="h-[460px] w-full bg-white" />
    </section>
  );
}
