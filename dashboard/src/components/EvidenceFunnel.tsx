import { useMemo, useState } from 'react';
import type { CatalogEntry } from '../catalog';
import type { PerformanceState } from '../hooks/useRunCatalog';
import { criticalT, medianRecordedSd, toFunnelPoints } from '../evidenceFunnel';
import type { FunnelPoint } from '../evidenceFunnel';

/**
 * Funnel plot over every published run: trade count against average R.
 *
 * The question it answers is "which of these results actually prove
 * anything?". A per-symbol table ranks runs by average R, which invites
 * reading a -0.30R run over 12 trades as worse than a -0.09R run over 800
 * -- when only the second one has enough trades to say anything at all.
 * Plotting average R against sample size makes that visible: the spread of
 * a mean narrows as sqrt(n), so the runs that carry evidence are the ones
 * that fall OUTSIDE a funnel that narrows with the same curve.
 *
 * Every quantity here is read from the producer's published summary. In
 * particular the dispersion (`result_r_sd`) is recorded per run, never
 * assumed. This chart was prototyped against an assumed SD of 1.0; the
 * measured values across the published catalog run 0.539 to 1.096, and the
 * assumption did NOT reproduce the recorded classification -- one run
 * (Strategy 02 v3 on DIA, 4 trades, SD 0.539) sits outside the funnel on
 * its recorded dispersion and inside it on an assumed 1.0. A run whose
 * bundle records no dispersion is drawn as unknown and given no verdict,
 * rather than being judged against a number nobody measured.
 */

interface EvidenceFunnelProps {
  entries: CatalogEntry[];
  performance: PerformanceState;
  onSelectRun?: (entry: CatalogEntry) => void;
}

const em = '—';

const VIEW_WIDTH = 900;
const VIEW_HEIGHT = 420;
const MARGIN = { top: 22, right: 26, bottom: 52, left: 66 };
const PLOT_WIDTH = VIEW_WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = VIEW_HEIGHT - MARGIN.top - MARGIN.bottom;

const formatR = (value: number): string => `${value >= 0 ? '+' : ''}${value.toFixed(3)}R`;
const formatT = (value: number | null): string => (value === null ? em : value.toFixed(2));
const formatSd = (value: number | null): string => (value === null ? em : value.toFixed(3));

/** Log-scale x. Trade counts start at 1, so log10 is always defined here. */
const logOf = (tradeCount: number) => Math.log10(Math.max(tradeCount, 1));

function niceDecades(minCount: number, maxCount: number): number[] {
  const ticks: number[] = [];
  for (let power = 0; power <= 5; power += 1) {
    const value = 10 ** power;
    if (value >= minCount / 2 && value <= maxCount * 2) ticks.push(value);
  }
  return ticks;
}

export function EvidenceFunnel({ entries, performance, onSelectRun }: EvidenceFunnelProps) {
  const [hovered, setHovered] = useState<FunnelPoint | null>(null);

  const model = useMemo(() => {
    const { points, unplottable, pending } = toFunnelPoints(entries, performance);
    if (points.length === 0) return null;

    const counts = points.map((point) => point.tradeCount);
    const minCount = Math.min(...counts);
    const maxCount = Math.max(...counts);
    const xMin = logOf(minCount) - 0.15;
    const xMax = logOf(maxCount) + 0.15;

    const maxAbsR = Math.max(...points.map((point) => Math.abs(point.averageR)), 0.1);
    const yBound = maxAbsR * 1.15;

    // The drawn boundary needs ONE dispersion, but every run records its
    // own. The median of the recorded values is used for the curve and
    // said so in the legend; each dot's own classification uses its own
    // recorded value, which is why a dot can sit marginally on the other
    // side of the drawn line from its label. Substituting the median for a
    // run that recorded nothing is exactly the assumption this chart
    // exists to avoid, so those runs get no classification at all.
    const medianSd = medianRecordedSd(points);

    const xScale = (tradeCount: number) =>
      MARGIN.left + ((logOf(tradeCount) - xMin) / (xMax - xMin)) * PLOT_WIDTH;
    const yScale = (averageR: number) =>
      MARGIN.top + ((yBound - averageR) / (2 * yBound)) * PLOT_HEIGHT;

    // Sample the boundary: |avg R| = criticalT(n-1) * sd / sqrt(n). The
    // critical value widens as n shrinks, so the funnel flares at the low-n
    // end rather than closing on a flat 2 standard errors.
    const upperXY: Array<[number, number]> = [];
    const lowerXY: Array<[number, number]> = [];
    if (medianSd !== null) {
      const steps = 120;
      for (let step = 0; step <= steps; step += 1) {
        const n = 10 ** (xMin + ((xMax - xMin) * step) / steps);
        const halfWidth = (criticalT(Math.max(1, n - 1)) * medianSd) / Math.sqrt(n);
        const x = MARGIN.left + (step / steps) * PLOT_WIDTH;
        upperXY.push([x, yScale(halfWidth)]);
        lowerXY.push([x, yScale(-halfWidth)]);
      }
    }
    const polyline = (pairs: Array<[number, number]>) =>
      pairs.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');

    const upper = upperXY.length ? polyline(upperXY) : '';
    const lower = lowerXY.length ? polyline(lowerXY) : '';
    const band = upperXY.length
      ? `${polyline(upperXY)} ${lowerXY
          .slice()
          .reverse()
          .map(([x, y]) => `L${x.toFixed(2)},${y.toFixed(2)}`)
          .join(' ')} Z`
      : '';

    const conclusive = points
      .filter((point) => point.isConclusive)
      .sort((a, b) => Math.abs(b.t ?? 0) - Math.abs(a.t ?? 0));
    const missingDispersion = points.filter((point) => point.resultRSd === null).length;

    return {
      points,
      unplottable,
      pending,
      conclusive,
      missingDispersion,
      medianSd,
      xScale,
      yScale,
      upper,
      lower,
      band,
      yBound,
      decades: niceDecades(minCount, maxCount),
    };
  }, [entries, performance]);

  if (!model) {
    return (
      <section className="s4-panel p-5">
        <div className="s4-eyebrow">Which results conclude anything</div>
        <p className="mt-2 text-xs text-slate-600">
          No run has published both a trade count and an average R yet.
        </p>
      </section>
    );
  }

  const { xScale, yScale } = model;
  const yTicks = [-model.yBound, -model.yBound / 2, 0, model.yBound / 2, model.yBound];

  return (
    <section className="s4-panel overflow-hidden">
      <div className="border-b border-slate-200 px-5 py-4">
        <div className="s4-eyebrow">Which results conclude anything</div>
        <h2 className="mt-1 text-base font-semibold text-slate-950">
          Average R against sample size, {model.points.length} run
          {model.points.length === 1 ? '' : 's'}
        </h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">
          The average of a few trades bounces around; the average of many settles down. The dashed
          funnel narrows at the same rate, so a run inside it has too few trades to conclude
          anything from, whatever its average R looks like. Only runs outside the funnel are
          conclusive.{' '}
          {model.conclusive.length > 0 && model.conclusive.every((point) => point.averageR < 0) && (
            <>
              Every one that currently qualifies concludes a <strong>loss</strong>, not an edge.{' '}
            </>
          )}
          Click any dot to open that run.
        </p>
      </div>

      <div className="s4-funnel-wrap relative px-5 py-4">
        <svg
          viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
          className="s4-funnel-svg w-full"
          role="img"
          aria-label={`Funnel plot of ${model.points.length} runs. ${model.conclusive.length} fall outside the funnel and are statistically conclusive; the rest have too few trades to conclude.`}
        >
          {/* Funnel interior: the region where a result is indistinguishable from no edge. */}
          {model.band && <path d={model.band} className="s4-funnel-band" />}

          {yTicks.map((value) => (
            <g key={`y-${value}`}>
              <line
                x1={MARGIN.left}
                x2={MARGIN.left + PLOT_WIDTH}
                y1={yScale(value)}
                y2={yScale(value)}
                className={value === 0 ? 's4-funnel-zero' : 's4-funnel-grid'}
              />
              <text x={MARGIN.left - 10} y={yScale(value) + 4} textAnchor="end" className="s4-funnel-tick">
                {value.toFixed(2)}
              </text>
            </g>
          ))}
          <text
            x={MARGIN.left + PLOT_WIDTH - 4}
            y={yScale(0) - 7}
            textAnchor="end"
            className="s4-funnel-axis-note"
          >
            no edge
          </text>

          {model.decades.map((value) => (
            <g key={`x-${value}`}>
              <line
                x1={xScale(value)}
                x2={xScale(value)}
                y1={MARGIN.top}
                y2={MARGIN.top + PLOT_HEIGHT}
                className="s4-funnel-grid"
              />
              <text
                x={xScale(value)}
                y={MARGIN.top + PLOT_HEIGHT + 18}
                textAnchor="middle"
                className="s4-funnel-tick"
              >
                {value.toLocaleString('en-US')}
              </text>
            </g>
          ))}

          {model.upper && <path d={model.upper} className="s4-funnel-boundary" />}
          {model.lower && <path d={model.lower} className="s4-funnel-boundary" />}

          <text
            x={MARGIN.left + PLOT_WIDTH / 2}
            y={VIEW_HEIGHT - 12}
            textAnchor="middle"
            className="s4-funnel-axis-label"
          >
            Trades in the run (log scale)
          </text>
          <text
            transform={`translate(16 ${MARGIN.top + PLOT_HEIGHT / 2}) rotate(-90)`}
            textAnchor="middle"
            className="s4-funnel-axis-label"
          >
            Average R per trade
          </text>

          {model.points.map((point) => (
            <circle
              key={point.entry.bundle_id}
              cx={xScale(point.tradeCount)}
              cy={yScale(point.averageR)}
              r={hovered?.entry.bundle_id === point.entry.bundle_id ? 7 : 4.5}
              className={
                point.isConclusive
                  ? 's4-funnel-dot is-conclusive'
                  : point.resultRSd === null
                    ? 's4-funnel-dot is-unknown'
                    : 's4-funnel-dot'
              }
              tabIndex={0}
              role="button"
              aria-label={`${point.entry.run.strategy_id} ${point.entry.run.strategy_version} ${
                point.entry.instrument.symbol || 'unknown symbol'
              }: ${point.tradeCount} trades, ${formatR(point.averageR)}, ${
                point.resultRSd === null
                  ? 'dispersion not recorded'
                  : point.isConclusive
                    ? 'conclusive'
                    : 'too few trades to conclude'
              }`}
              onMouseEnter={() => setHovered(point)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(point)}
              onBlur={() => setHovered(null)}
              onClick={() => onSelectRun?.(point.entry)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                onSelectRun?.(point.entry);
              }}
            />
          ))}
        </svg>

        {hovered && (
          <div className="s4-funnel-tooltip" role="status">
            <div className="font-semibold">
              {hovered.entry.run.strategy_id} {hovered.entry.run.strategy_version}
            </div>
            <div className="s4-funnel-tooltip-sub">
              {hovered.entry.run.run_id}
              {hovered.entry.instrument.symbol ? ` · ${hovered.entry.instrument.symbol}` : ''}
            </div>
            <dl className="s4-funnel-tooltip-grid">
              <dt>Trades</dt>
              <dd>{hovered.tradeCount.toLocaleString('en-US')}</dd>
              <dt>Avg R</dt>
              <dd>{formatR(hovered.averageR)}</dd>
              <dt>SD of R</dt>
              <dd>{formatSd(hovered.resultRSd)}</dd>
              <dt>t</dt>
              <dd>{formatT(hovered.t)}</dd>
            </dl>
            <div className="s4-funnel-tooltip-verdict">
              {hovered.resultRSd === null
                ? 'This run did not record the dispersion of its results, so whether it concludes anything cannot be determined.'
                : hovered.isConclusive
                  ? `Conclusive: outside the funnel. The result is ${
                      hovered.averageR < 0 ? 'a loss' : 'a gain'
                    } too large to be sample noise.`
                  : 'Too few trades to conclude: inside the funnel, this average is consistent with no edge.'}
            </div>
          </div>
        )}

        <ul className="s4-funnel-legend">
          <li>
            <span className="s4-funnel-key is-conclusive" aria-hidden="true" />
            Outside the funnel — conclusive
          </li>
          <li>
            <span className="s4-funnel-key" aria-hidden="true" />
            Inside the funnel — too few trades to conclude
          </li>
          <li>
            <span className="s4-funnel-key is-unknown" aria-hidden="true" />
            Dispersion not recorded — cannot be judged
          </li>
          <li>
            <span className="s4-funnel-key is-line" aria-hidden="true" />
            {model.medianSd === null
              ? 'Funnel boundary (no dispersion recorded)'
              : `Funnel boundary, |avg R| = t₉₅(n−1) × SD / √trades, drawn at the median recorded SD of ${model.medianSd.toFixed(
                  3,
                )}`}
          </li>
        </ul>

        {model.medianSd !== null && (
          <p className="mt-2 text-[11px] leading-4 text-slate-500">
            Each dot is classified against its own recorded SD, not the median the curve is drawn
            at, so a dot near the boundary may sit fractionally on the other side of the drawn line
            from its verdict.
            {model.missingDispersion > 0 &&
              ` ${model.missingDispersion} of ${model.points.length} runs recorded no dispersion.`}
            {model.unplottable > 0 &&
              ` ${model.unplottable} run${
                model.unplottable === 1 ? '' : 's'
              } published no trade count or average R and cannot be placed at all.`}
            {model.pending > 0 &&
              ` ${model.pending} run${model.pending === 1 ? ' is' : 's are'} still loading and not
                yet plotted.`}
          </p>
        )}
      </div>

      <div className="border-t border-slate-200 px-5 py-4">
        <h3 className="text-sm font-semibold text-slate-950">
          {model.conclusive.length} run{model.conclusive.length === 1 ? '' : 's'} outside the funnel
        </h3>
        {model.conclusive.length === 0 ? (
          <p className="mt-1 text-xs text-slate-600">
            No run has enough trades relative to its own spread to conclude anything.
          </p>
        ) : (
          <>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">
              These are the only runs whose result is too large to be sample noise. A negative
              average R here is a measured losing edge, not an unlucky sample. The boundary uses
              the 95% critical value of Student&rsquo;s t for each run&rsquo;s own degrees of
              freedom, so it widens as the sample shrinks — at four trades the bar is 3.18 standard
              errors, not 2. Read the trade count alongside the verdict all the same: a spread
              measured from a handful of trades is itself uncertain.
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="s4-compare-table min-w-[720px]">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Run</th>
                    <th>Symbol</th>
                    <th>Trades</th>
                    <th>Avg R</th>
                    <th>SD of R</th>
                    <th>t</th>
                  </tr>
                </thead>
                <tbody>
                  {model.conclusive.map((point) => (
                    <tr
                      key={point.entry.bundle_id}
                      className="s4-row-button hover:bg-indigo-50/50"
                      tabIndex={0}
                      role="button"
                      aria-label={`Open ${point.entry.run.strategy_id} ${point.entry.run.run_id}`}
                      onClick={() => onSelectRun?.(point.entry)}
                      onKeyDown={(event) => {
                        if (event.key !== 'Enter' && event.key !== ' ') return;
                        event.preventDefault();
                        onSelectRun?.(point.entry);
                      }}
                    >
                      <td>
                        <div className="font-semibold text-slate-950">
                          {point.entry.run.strategy_id}
                        </div>
                        <div className="mt-0.5 text-[11px] font-normal text-slate-500">
                          {point.entry.run.strategy_version}
                        </div>
                      </td>
                      <td className="text-left font-normal">{point.entry.run.run_id}</td>
                      <td>{point.entry.instrument.symbol || em}</td>
                      <td>{point.tradeCount.toLocaleString('en-US')}</td>
                      <td className={point.averageR >= 0 ? 'text-emerald-700' : 'text-rose-700'}>
                        {formatR(point.averageR)}
                      </td>
                      <td>{formatSd(point.resultRSd)}</td>
                      <td>{formatT(point.t)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
