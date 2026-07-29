import { useEffect, useState } from 'react';
import type { Bar, ExitReason, TradeSide } from './types';
import type { Strategy04Asset, Strategy04Version } from './strategy04Data';

export interface AuditCheck {
  check_id: string;
  passed: boolean;
  expected: string;
  actual: string;
}

export interface AuditResult {
  passed: boolean;
  checks: AuditCheck[];
}

export interface FixtureZone {
  zone_id: number;
  side: 'demand' | 'supply';
  lower: number;
  upper: number;
  qualified_timestamp: string;
  score: number;
}

export interface FixtureBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AuditedTrade {
  trade_id: string;
  ordinal: number;
  decision_timestamp: string;
  entry_timestamp: string;
  exit_timestamp: string;
  side: TradeSide;
  entry_price: number;
  stop_price: number;
  target_price: number;
  exit_price: number;
  exit_reason: ExitReason;
  result_r: number;
  trigger_timestamp: string;
  audit: AuditResult;
  zones: { selected: FixtureZone; competing: FixtureZone[] };
  bars: { one_hour: FixtureBar[]; fifteen_minute: FixtureBar[] };
}

export interface Strategy04Fixture {
  schema_version: string;
  bundle_id: string;
  execution_authority: string;
  run: { strategy_id: string; strategy_version: string };
  instrument: { symbol: string };
  summary: {
    trade_count: number;
    audit_passed: number;
    audit_failed: number;
    net_pnl: number;
    ending_equity: number;
  };
  trades: AuditedTrade[];
}

/**
 * Every strategy version / asset combination that has a generated audit
 * fixture, keyed the same way the dashboard's version and asset pickers are.
 * A combination with no fixture on disk is simply absent from its version's
 * row -- callers must not assume every asset is present.
 *
 * These are `import()` thunks rather than static imports. Each fixture
 * carries a bar window per trade, so the six together are about 10 MB of
 * JSON; importing them eagerly put all six in the entry chunk and every
 * visitor downloaded all of them to look at one. Vite gives each its own
 * chunk, so only the selected version/asset is ever fetched.
 */
const FIXTURE_LOADERS: Record<
  Strategy04Version,
  Partial<Record<Strategy04Asset, () => Promise<{ default: unknown }>>>
> = {
  v1: {
    SPY: () => import('./fixtures/strategy_04_v1_spy.json'),
    QQQ: () => import('./fixtures/strategy_04_v1_qqq.json'),
    DIA: () => import('./fixtures/strategy_04_v1_dia.json'),
  },
  v1_1: {
    SPY: () => import('./fixtures/strategy_04_v1_1_spy.json'),
    QQQ: () => import('./fixtures/strategy_04_v1_1_qqq.json'),
    DIA: () => import('./fixtures/strategy_04_v1_1_dia.json'),
  },
};

/** True when a fixture was generated for this pair, without loading it. */
export const hasStrategy04Fixture = (
  version: Strategy04Version,
  asset: Strategy04Asset,
): boolean => Boolean(FIXTURE_LOADERS[version]?.[asset]);

const loaded = new Map<string, Promise<Strategy04Fixture>>();

/**
 * Load the audit fixture for a version/asset pair, or undefined if it was
 * never generated. Resolved fixtures are kept so switching back to a pair
 * does not refetch its chunk.
 */
export const loadStrategy04Fixture = (
  version: Strategy04Version,
  asset: Strategy04Asset,
): Promise<Strategy04Fixture> | undefined => {
  const loader = FIXTURE_LOADERS[version]?.[asset];
  if (!loader) return undefined;
  const key = `${version}:${asset}`;
  const hit = loaded.get(key);
  if (hit) return hit;
  const pending = loader().then((module) => module.default as Strategy04Fixture);
  loaded.set(key, pending);
  return pending;
};

export const toEpochSeconds = (timestamp: string): number =>
  Math.floor(new Date(timestamp).getTime() / 1000);

export const toChartBars = (bars: FixtureBar[]): Bar[] =>
  bars.map((bar) => ({
    time: toEpochSeconds(bar.timestamp),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  }));

export const failedChecks = (trade: AuditedTrade): AuditCheck[] =>
  trade.audit.checks.filter((check) => !check.passed);

export type FixtureStatus = 'loading' | 'loaded' | 'absent';

/**
 * Load the fixture for the selected version/asset, tracking whether it is
 * still in flight. `absent` means no fixture was ever generated for the pair,
 * which is a different thing from one that is still downloading -- the two
 * must not render the same message.
 */
export function useStrategy04Fixture(
  version: Strategy04Version,
  asset: Strategy04Asset,
): { status: FixtureStatus; fixture: Strategy04Fixture | null } {
  const [state, setState] = useState<{
    status: FixtureStatus;
    fixture: Strategy04Fixture | null;
  }>(() => ({
    status: hasStrategy04Fixture(version, asset) ? 'loading' : 'absent',
    fixture: null,
  }));

  useEffect(() => {
    const pending = loadStrategy04Fixture(version, asset);
    if (!pending) {
      setState({ status: 'absent', fixture: null });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading', fixture: null });
    pending
      .then((fixture) => {
        if (cancelled) return;
        setState({ status: 'loaded', fixture });
      })
      .catch(() => {
        if (cancelled) return;
        setState({ status: 'absent', fixture: null });
      });
    return () => {
      cancelled = true;
    };
  }, [version, asset]);

  return state;
}
