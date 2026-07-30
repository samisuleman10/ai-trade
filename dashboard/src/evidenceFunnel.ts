import type { CatalogEntry } from './catalog';
import type { PerformanceState, PerformanceSummary } from './hooks/useRunCatalog';

/**
 * The arithmetic behind the evidence funnel, kept out of the component so
 * the classification rule is readable on its own.
 *
 * Every input is a number the producer published. Nothing here supplies a
 * default for a missing one -- in particular, a run whose bundle records
 * no `result_r_sd` gets no t-statistic and no verdict, rather than being
 * judged against an assumed dispersion. The measured spread across this
 * repository's runs is 0.672 to 1.096, so any assumed constant is simply
 * wrong for most runs; that it happens to sort the current catalog
 * correctly is luck and not something to build on.
 */

/**
 * How many standard errors from zero a result must sit before this chart
 * calls it conclusive. Two is the conventional ~95% two-sided threshold.
 * The drawn boundary and each dot's verdict both read this constant, so
 * they cannot drift apart.
 */
export const SIGMA = 2;

/** A run reduced to the published numbers the funnel needs. */
export interface FunnelPoint {
  entry: CatalogEntry;
  tradeCount: number;
  averageR: number;
  /** Producer-recorded dispersion of result_r, or null when unrecorded. */
  resultRSd: number | null;
  /** averageR * sqrt(n) / sd, or null when the dispersion was not recorded. */
  t: number | null;
  /** True only when a RECORDED dispersion puts |t| at or beyond SIGMA. */
  isConclusive: boolean;
}

export interface FunnelPoints {
  points: FunnelPoint[];
  /** Runs with no trade count or no average R: placeable on neither axis. */
  unplottable: number;
}

/**
 * Reduce the catalog to plottable points.
 *
 * A run missing `trade_count` or `average_r` cannot be placed on either
 * axis and is counted as unplottable rather than silently dropped. A run
 * with a position but no recorded dispersion IS plotted -- its coordinates
 * are real -- but never classified, because classifying would require a
 * standard deviation nobody recorded.
 */
export function toFunnelPoints(
  entries: CatalogEntry[],
  performance: PerformanceState,
): FunnelPoints {
  const points: FunnelPoint[] = [];
  let unplottable = 0;

  for (const entry of entries) {
    const summary: PerformanceSummary | undefined = performance[entry.bundle_id]?.summary;
    const tradeCount = summary?.trade_count;
    const averageR = summary?.average_r;
    if (typeof tradeCount !== 'number' || tradeCount < 1 || typeof averageR !== 'number') {
      unplottable += 1;
      continue;
    }

    const recorded = summary?.result_r_sd;
    const resultRSd = typeof recorded === 'number' && recorded > 0 ? recorded : null;
    const t = resultRSd === null ? null : (averageR * Math.sqrt(tradeCount)) / resultRSd;

    points.push({
      entry,
      tradeCount,
      averageR,
      resultRSd,
      t,
      isConclusive: t !== null && Math.abs(t) >= SIGMA,
    });
  }

  return { points, unplottable };
}

/**
 * Median of the recorded dispersions, or null when none were recorded.
 *
 * Used ONLY to draw a single boundary curve -- one curve cannot represent
 * 68 different standard deviations. Each dot is still classified against
 * its own value, and the chart says so.
 */
export function medianRecordedSd(points: FunnelPoint[]): number | null {
  const recorded = points
    .map((point) => point.resultRSd)
    .filter((value): value is number => value !== null)
    .sort((a, b) => a - b);
  if (recorded.length === 0) return null;
  const middle = Math.floor(recorded.length / 2);
  return recorded.length % 2 === 1
    ? recorded[middle]
    : (recorded[middle - 1] + recorded[middle]) / 2;
}
