import type { DeepDiveConfig } from './strategy04Config';
import { strategy04Config } from './strategy04Config';

/**
 * Which strategies have a deep-dive screen, newest first.
 *
 * `App` builds its tab bar from this list and opens the first entry, so a new
 * strategy's screen becomes the landing screen by adding one entry here --
 * the convention this file replaces was a hand-edited `SECTIONS` array.
 * A strategy only belongs here once it has a view of its own; 01, 02 and 03
 * live in Compare and All runs instead.
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

export const DEEP_DIVES: DeepDiveEntry[] = [
  {
    id: 'strategy04',
    label: 'Strategy 04',
    familyId: 'strategy_04',
    footerLabel: 'strategy_04 deep dive',
    config: strategy04Config,
  },
];
