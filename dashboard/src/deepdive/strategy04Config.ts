import {
  STRATEGY_04_SPECS,
  STRATEGY_04_VARIANTS,
  STRATEGY_04_VERSIONS,
} from '../strategy04Data';
import type { Strategy04Spec } from '../strategy04Data';
import { STRATEGY_04_ASSETS } from '../strategy04Summary';

/**
 * Shape a strategy's deep-dive screen renders from.
 *
 * `versions`, `variantsByVersion` and `assets` use plain string ids so the
 * screen component itself never needs to know a strategy's literal id
 * unions -- those stay in that strategy's own data module (e.g.
 * `strategy04Data.ts`) and are only widened to `string` here, at the
 * boundary the shared component consumes.
 */
export interface DeepDiveConfig {
  familyId: string;
  title: string;
  subtitle: string;
  versions: Array<{ id: string; label: string; description: string }>;
  variantsByVersion: Record<string, Array<{ id: string; label: string; description: string }>>;
  assets: string[];
  specs: Record<string, Strategy04Spec>;
  /**
   * Which version/variant the deep dive should land on. Declared explicitly
   * rather than left to fall out of `versions[0]`/`variantsByVersion[...][0]`
   * order, so a reorder of either array can't silently change the first
   * paint. Strategy 04 opens on its newest version (matching the repo's
   * newest-first convention for both tabs and version chips) with the Base
   * variant, since v1.2/Base reproduces the previous incumbent (v1.1)
   * exactly -- a returning user sees the same numbers as before.
   */
  defaultVersionId: string;
  defaultVariantId: string;
  /**
   * Human-readable "change from" prefixes, keyed by version id. Populated
   * per strategy rather than hard-coded in the shared component so a second
   * strategy family with different version ids renders its own labels
   * instead of `undefined`. Versions with no entry simply render their
   * change text without a prefix.
   */
  changeFromLabels: Record<string, string>;
}

/**
 * Strategy 04's deep-dive config, assembled from its existing data module --
 * nothing here is re-typed or re-transcribed, only re-exposed in the shape
 * the shared deep-dive screen expects.
 */
export const strategy04Config: DeepDiveConfig = {
  familyId: 'strategy_04',
  title: 'Strategy 04',
  subtitle: 'Causal 1H zones · 15M reaction entries',
  versions: STRATEGY_04_VERSIONS,
  variantsByVersion: { v1_2: STRATEGY_04_VARIANTS },
  assets: STRATEGY_04_ASSETS,
  specs: STRATEGY_04_SPECS,
  defaultVersionId: 'v1_2',
  defaultVariantId: 'base',
  changeFromLabels: {
    v1: 'Change from v1.0:',
    v1_1: 'Change from v1.0:',
    v1_2: 'Change from v1.1:',
  },
};
