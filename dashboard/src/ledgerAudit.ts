import { useEffect, useState } from 'react';
import { fetchDataset } from './catalog';

/**
 * The `trade_audit` dataset, as every published run now carries it.
 *
 * `strategy04Audit.ts` reads the same dataset, but only as one of four it
 * joins into a per-trade deep dive with zone geometry and bar windows --
 * which only Strategy 04 publishes. This module reads the audit alone, which
 * is all a run needs to say whether its ledger checked out.
 *
 * The check shape is defined here and re-exported by `strategy04Audit`, so
 * both views read one type. The producer emits one type too
 * (`ledger_audit.CheckResult`): a Strategy 04 entry is its ledger checks
 * followed by its signal checks, in one list, under one `passed` flag.
 */
export interface AuditCheck {
  check_id: string;
  passed: boolean;
  expected: string;
  actual: string;
}

export interface AuditedTradeRow {
  trade_id: string;
  trigger_timestamp?: string;
  passed: boolean;
  checks: AuditCheck[];
}

export interface TradeAuditDataset {
  summary?: { audit_passed?: number; audit_failed?: number };
  trades: AuditedTradeRow[];
}

export interface AuditFailure {
  trade_id: string;
  check: AuditCheck;
}

/** Every failed check across the run, flattened, in ledger order. */
export function auditFailures(dataset: TradeAuditDataset): AuditFailure[] {
  const failures: AuditFailure[] = [];
  dataset.trades.forEach((trade) => {
    trade.checks.forEach((check) => {
      if (!check.passed) failures.push({ trade_id: trade.trade_id, check });
    });
  });
  return failures;
}

/**
 * Trades that failed at least one check, counted from the checks themselves.
 *
 * Deliberately not read from the dataset's `summary`. The producer derives
 * that summary from the same checks, so the two agree today -- but a
 * displayed count that cannot disagree with the evidence beneath it is
 * worth more than one that is merely expected to.
 */
export function failedTradeCount(dataset: TradeAuditDataset): number {
  return dataset.trades.filter((trade) => trade.checks.some((check) => !check.passed)).length;
}

export type RunAuditStatus = 'absent' | 'loading' | 'loaded' | 'error';

/**
 * Fetch one run's trade audit.
 *
 * `absent` means the bundle publishes no audit at all -- true of any bundle
 * published before the ledger checks existed, and it must not be shown as a
 * clean result. `error` means the request failed, which is not a verdict
 * either. Only `loaded` carries one.
 */
export function useRunAudit(
  bundleId: string,
  hasAudit: boolean,
): { status: RunAuditStatus; dataset: TradeAuditDataset | null } {
  const [state, setState] = useState<{
    status: RunAuditStatus;
    dataset: TradeAuditDataset | null;
  }>({ status: hasAudit ? 'loading' : 'absent', dataset: null });

  useEffect(() => {
    if (!hasAudit) {
      setState({ status: 'absent', dataset: null });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading', dataset: null });

    fetchDataset<TradeAuditDataset>(bundleId, 'trade_audit')
      .then((dataset) => {
        if (cancelled) return;
        setState({ status: 'loaded', dataset });
      })
      .catch(() => {
        if (cancelled) return;
        setState({ status: 'error', dataset: null });
      });

    return () => {
      cancelled = true;
    };
  }, [bundleId, hasAudit]);

  return state;
}
