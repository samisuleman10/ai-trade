import fixtureV1Spy from './fixtures/strategy_04_v1_spy.json';
import fixtureV1Qqq from './fixtures/strategy_04_v1_qqq.json';
import fixtureV1Dia from './fixtures/strategy_04_v1_dia.json';
import fixtureV1_1Spy from './fixtures/strategy_04_v1_1_spy.json';
import fixtureV1_1Qqq from './fixtures/strategy_04_v1_1_qqq.json';
import fixtureV1_1Dia from './fixtures/strategy_04_v1_1_dia.json';
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
 */
export const STRATEGY_04_FIXTURES: Record<
  Strategy04Version,
  Partial<Record<Strategy04Asset, Strategy04Fixture>>
> = {
  v1: {
    SPY: fixtureV1Spy as unknown as Strategy04Fixture,
    QQQ: fixtureV1Qqq as unknown as Strategy04Fixture,
    DIA: fixtureV1Dia as unknown as Strategy04Fixture,
  },
  v1_1: {
    SPY: fixtureV1_1Spy as unknown as Strategy04Fixture,
    QQQ: fixtureV1_1Qqq as unknown as Strategy04Fixture,
    DIA: fixtureV1_1Dia as unknown as Strategy04Fixture,
  },
};

/** Look up the audit fixture for a version/asset pair, or undefined if it was never generated. */
export const getStrategy04Fixture = (
  version: Strategy04Version,
  asset: Strategy04Asset,
): Strategy04Fixture | undefined => STRATEGY_04_FIXTURES[version]?.[asset];

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
