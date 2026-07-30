import { useEffect, useState } from 'react';
import { fetchDataset, fetchRuns } from './catalog';
import { familyOf } from './strategyDescriptions';
import type { Bar, ExitReason, TradeSide } from './types';
import type { AuditCheck } from './ledgerAudit';

/**
 * One check shape for both audits, mirroring the producer.
 *
 * A Strategy 04 trade's `trade_audit` entry is its ledger checks followed
 * by its signal checks, in one list under one `passed` flag -- both emitted
 * as `ledger_audit.CheckResult`. Declaring a second, identical interface
 * here would let the two drift apart on this side of the wire.
 */
export type { AuditCheck };

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
  version: string,
  asset: string,
  variant: string,
  familyId: string,
): { status: AuditStatus; trades: AuditedTrade[] } {
  const [state, setState] = useState<{ status: AuditStatus; trades: AuditedTrade[] }>({
    status: 'loading',
    trades: [],
  });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', trades: [] });

    const load = async () => {
      // The catalog's strategy_id filter is exact equality against the
      // producer's full id (`strategy_04_v1_1_shallow_long_penetration`), so
      // filtering on the family name server-side matches nothing. Narrow by
      // version and symbol, then pick the Strategy 04 family here.
      //
      // `trade_audit` alone is not enough: bundles published through the
      // lightweight per-run path (every FX v1.1 run, every v1.2 run so far)
      // carry ledger checks in `trade_audit` but never publish `zones` or
      // `audit_windows` -- those need the repository's bar caches, which
      // only the full backfill pass can reach. Without this check the
      // dataset fetch below 404s on `zones`/`audit_windows` and the whole
      // panel reports "Catalog API unreachable", which is false: the
      // server is fine, this run's chart-capable audit just was never
      // published.
      const runs = await fetchRuns({ strategy_version: version, symbol: asset });
      const entry = runs.find((run) => {
        if (familyOf(run.run.strategy_id) !== familyId) return false;
        if (!run.dataset_ids.includes('trade_audit')) return false;
        if (!run.dataset_ids.includes('zones') || !run.dataset_ids.includes('audit_windows')) {
          return false;
        }
        if (version === 'v1_2') return run.bundle_id.endsWith(`_${variant}`);
        return true;
      });
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
  }, [version, asset, variant, familyId]);

  return state;
}
