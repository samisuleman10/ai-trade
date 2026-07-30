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
};
