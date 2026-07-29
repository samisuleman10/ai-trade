import { useEffect, useState } from 'react';
import { fetchDataset, fetchRuns } from './catalog';
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

export interface AuditZone {
  zone_id: number;
  side: 'demand' | 'supply';
  lower: number;
  upper: number;
  qualified_timestamp: string;
  score: number;
}

export interface AuditBar {
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
  zones: { selected: AuditZone; competing: AuditZone[] };
  bars: { one_hour: AuditBar[]; fifteen_minute: AuditBar[] };
}

interface LedgerDataset {
  trades: Array<Record<string, unknown>>;
}
interface AuditDataset {
  trades: Array<{ trade_id: string; trigger_timestamp: string; passed: boolean; checks: AuditCheck[] }>;
}
interface ZonesDataset {
  trades: Array<{ trade_id: string; selected: AuditZone; competing: AuditZone[] }>;
}
interface WindowsDataset {
  trades: Array<{ trade_id: string; one_hour: AuditBar[]; fifteen_minute: AuditBar[] }>;
}

const byTradeId = <T extends { trade_id: string }>(rows: T[]): Map<string, T> =>
  new Map(rows.map((row) => [row.trade_id, row]));

/**
 * Join a run's trade ledger to its audit datasets.
 *
 * The ledger is the single source for prices, sides and outcomes; the audit
 * datasets add only checks, zones and bars. A trade the audit does not cover
 * is dropped rather than rendered with an empty check list, because a row
 * showing no failures has to mean "checked and passed", never "not checked".
 */
export function assembleAuditedTrades(
  ledger: LedgerDataset,
  audit: AuditDataset,
  zones: ZonesDataset,
  windows: WindowsDataset,
): AuditedTrade[] {
  const auditById = byTradeId(audit.trades);
  const zonesById = byTradeId(zones.trades);
  const windowsById = byTradeId(windows.trades);

  const assembled: AuditedTrade[] = [];
  ledger.trades.forEach((row, index) => {
    const tradeId = String(row.trade_id);
    const auditRow = auditById.get(tradeId);
    const zoneRow = zonesById.get(tradeId);
    const windowRow = windowsById.get(tradeId);
    if (!auditRow || !zoneRow || !windowRow) return;
    assembled.push({
      ...(row as unknown as AuditedTrade),
      ordinal: index + 1,
      trigger_timestamp: auditRow.trigger_timestamp,
      audit: { passed: auditRow.passed, checks: auditRow.checks },
      zones: { selected: zoneRow.selected, competing: zoneRow.competing },
      bars: { one_hour: windowRow.one_hour, fifteen_minute: windowRow.fifteen_minute },
    });
  });
  return assembled;
}

export const toEpochSeconds = (timestamp: string): number =>
  Math.floor(new Date(timestamp).getTime() / 1000);

export const toChartBars = (bars: AuditBar[]): Bar[] =>
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

export type AuditStatus = 'loading' | 'loaded' | 'absent' | 'error';

/**
 * Resolve a version/asset pair to a published bundle, then fetch its audit.
 *
 * The three states a caller must keep apart: `absent` means no bundle for
 * that pair publishes an audit, `error` means the catalog API could not be
 * reached, and an empty `trades` array on `loaded` means the run genuinely
 * produced no trades. Collapsing any of these would report a stopped server
 * as a strategy that never traded.
 */
export function useStrategy04Audit(
  version: Strategy04Version,
  asset: Strategy04Asset,
): { status: AuditStatus; trades: AuditedTrade[] } {
  const [state, setState] = useState<{ status: AuditStatus; trades: AuditedTrade[] }>({
    status: 'loading',
    trades: [],
  });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', trades: [] });

    const load = async () => {
      const runs = await fetchRuns({
        strategy_id: 'strategy_04',
        strategy_version: version,
        symbol: asset,
      });
      const entry = runs.find((run) => run.dataset_ids.includes('trade_audit'));
      if (!entry) {
        if (!cancelled) setState({ status: 'absent', trades: [] });
        return;
      }
      const [ledger, audit, zones, windows] = await Promise.all([
        fetchDataset<LedgerDataset>(entry.bundle_id, 'trades_fixed'),
        fetchDataset<AuditDataset>(entry.bundle_id, 'trade_audit'),
        fetchDataset<ZonesDataset>(entry.bundle_id, 'zones'),
        fetchDataset<WindowsDataset>(entry.bundle_id, 'audit_windows'),
      ]);
      if (cancelled) return;
      setState({
        status: 'loaded',
        trades: assembleAuditedTrades(ledger, audit, zones, windows),
      });
    };

    load().catch(() => {
      if (!cancelled) setState({ status: 'error', trades: [] });
    });

    return () => {
      cancelled = true;
    };
  }, [version, asset]);

  return state;
}
