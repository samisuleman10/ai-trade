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
 * published catalog is 0.539 to 1.096, so any assumed constant is simply
 * wrong for most runs -- and an assumed 1.0 puts one run on the wrong side
 * of the boundary outright.
 */

/**
 * Two-sided 95% critical values of Student's t, by degrees of freedom.
 *
 * A flat 2.0 is the large-sample limit and is wrong for small runs: at 4
 * trades (3 df) the bar is 3.182, not 2.0. Using 2.0 there marked a
 * four-trade run as conclusive — in a chart whose entire purpose is to
 * stop small samples being over-read. The threshold has to widen as the
 * sample shrinks, which is exactly what these values do.
 */
const T_TABLE: Array<[df: number, critical: number]> = [
  [1, 12.706], [2, 4.303], [3, 3.182], [4, 2.776], [5, 2.571],
  [6, 2.447], [7, 2.365], [8, 2.306], [9, 2.262], [10, 2.228],
  [12, 2.179], [15, 2.131], [20, 2.086], [25, 2.06], [30, 2.042],
  [40, 2.021], [60, 2.0], [120, 1.98],
];

/** The large-sample limit the table converges to. */
export const SIGMA_LIMIT = 1.96;

/**
 * Critical |t| for `df` degrees of freedom, interpolated in 1/df because
 * the curve is close to linear in that space and badly non-linear in df.
 */
export function criticalT(df: number): number {
  if (df < 1) return T_TABLE[0][1];
  if (df >= 120) return SIGMA_LIMIT;
  for (let i = 0; i < T_TABLE.length - 1; i += 1) {
    const [dfLow, tLow] = T_TABLE[i];
    const [dfHigh, tHigh] = T_TABLE[i + 1];
    if (df === dfLow) return tLow;
    if (df < dfHigh) {
      const weight = (1 / df - 1 / dfLow) / (1 / dfHigh - 1 / dfLow);
      return tLow + weight * (tHigh - tLow);
    }
  }
  return SIGMA_LIMIT;
}

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
  /** Runs whose dataset has arrived but records no trade count or average R. */
  unplottable: number;
  /** Runs whose dataset request is still in flight. NOT the same as unplottable. */
  pending: number;
}

/**
 * Reduce the catalog to plottable points.
 *
 * A run whose dataset has arrived but records no `trade_count` or
 * `average_r` cannot be placed on either axis and is counted as
 * unplottable rather than silently dropped. A run still being fetched is
 * counted separately: the catalog fans out one request per run, so for the
 * first seconds most runs have no numbers yet, and reporting those as
 * "published nothing" would be a false statement about the producer.
 *
 * A run with a position but no recorded dispersion IS plotted -- its
 * coordinates are real -- but never classified, because classifying would
 * require a standard deviation nobody recorded.
 */
export function toFunnelPoints(
  entries: CatalogEntry[],
  performance: PerformanceState,
): FunnelPoints {
  const points: FunnelPoint[] = [];
  let unplottable = 0;
  let pending = 0;

  for (const entry of entries) {
    const state = performance[entry.bundle_id];
    if (state === undefined || state.status === 'loading') {
      pending += 1;
      continue;
    }
    const summary: PerformanceSummary | undefined = state.summary;
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
      isConclusive: t !== null && Math.abs(t) >= criticalT(tradeCount - 1),
    });
  }

  return { points, unplottable, pending };
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

/**
 * Human name for a Strategy 04 v1.2 ablation variant.
 *
 * The variant lives only in the run id's suffix (`..._ab`), which readers
 * have to decode from the spec. Guarded on the strategy id so a run from
 * another strategy that happens to end in `_a` is never mislabelled.
 */
export function variantLabel(strategyId: string, runId: string): string | null {
  if (!strategyId.includes('v1_2')) return null;
  if (runId.endsWith('_ab')) return 'Filter A + B';
  if (runId.endsWith('_a')) return 'Filter A only';
  if (runId.endsWith('_b')) return 'Filter B only';
  if (runId.endsWith('_base')) return 'No filters (v1.1 baseline)';
  return null;
}
