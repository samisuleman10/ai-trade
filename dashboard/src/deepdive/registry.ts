import type { DeepDiveConfig } from './strategy04Config';
import { strategy04Config } from './strategy04Config';
import strategiesJson from '../generated/strategies.json';

/**
 * Which strategies have a deep-dive screen, newest first.
 *
 * `App` builds its tab bar from this list and opens the first entry. Strategy
 * *identity* -- which strategies exist, their tab label, family id -- now
 * comes from the Python registry via the generated `strategies.json`
 * (regenerate with `python -m ai_trade.export_strategy_registry`), so a new
 * strategy registered in Python appears here without re-typing its name in
 * TypeScript. Only the rich display config below stays hand-written.
 */
export interface DeepDiveEntry {
  /** Stable tab id, also the nav key. */
  id: string;
  /** Tab label. */
  label: string;
  /** Catalog strategy family, e.g. `strategy_04`. */
  familyId: string;
  /** Footer provenance line shown while this tab is open. */
  footerLabel: string;
  /** Everything the shared deep-dive screen needs to render this strategy. */
  config: DeepDiveConfig;
}

/**
 * The hand-written display layer, keyed by family id. Version chips, variant
 * descriptions and spec prose are editorial content -- they read better
 * authored in TS next to the components that render them than round-tripped
 * through a Python exporter, so only identity is generated.
 */
const CONFIGS_BY_FAMILY: Record<string, DeepDiveConfig | undefined> = {
  strategy_04: strategy04Config,
};

export const DEEP_DIVES: DeepDiveEntry[] = [...strategiesJson.strategies]
  // The JSON lists strategies in registry order, oldest first; tabs go newest
  // leftmost so the newest strategy is the landing screen.
  .reverse()
  .flatMap((strategy) => {
    const config = CONFIGS_BY_FAMILY[strategy.strategy_id];
    if (!config) {
      // A registry strategy with no hand-written config gets no tab, by
      // design: strategies 01-03 have no bespoke screen and live in Compare
      // and All runs instead, and a placeholder deep dive would present an
      // empty screen as if it were published evidence. Skipping (rather than
      // crashing or placeholding) keeps the tab bar valid whatever Python
      // registers next.
      return [];
    }
    return [
      {
        // `strategy_04` -> `strategy04`: preserves the tab ids that predate
        // generation, so nav state and any saved links keep meaning the same
        // screen.
        id: strategy.strategy_id.replace(/_/g, ''),
        label: strategy.title,
        familyId: strategy.strategy_id,
        footerLabel: `${strategy.strategy_id} deep dive`,
        config,
      },
    ];
  });
