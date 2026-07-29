/**
 * Plain-language descriptions of what each strategy does.
 *
 * The catalog lists 48 runs across four strategies and seventeen strategy ids.
 * Without these, a row is an opaque identifier. Family summaries answer "what
 * is this strategy?", condition lines answer "what does this version change?".
 *
 * Every entry is drawn from the strategy documents under `strategies/`, not
 * inferred from the identifier text.
 */

export interface StrategyFamily {
  label: string;
  summary: string;
}

export const STRATEGY_FAMILIES: Record<string, StrategyFamily> = {
  strategy_01: {
    label: 'Strategy 01',
    summary:
      'Bill Williams Alligator with Heikin Ashi confirmation. A higher timeframe sets the trend, a lower one times the entry.',
  },
  strategy_02: {
    label: 'Strategy 02',
    summary:
      'Reversal setup. A one-hour Heikin Ashi candle crosses its Jaw against a still-open Alligator, confirmed by fifteen-minute Alligator alignment and a ZigZag level.',
  },
  strategy_03: {
    label: 'Strategy 03',
    summary:
      'Alligator mouth opening on a single timeframe, deliberately with no confirmation filters, to test whether that signal alone carries an edge.',
  },
  strategy_04: {
    label: 'Strategy 04',
    summary:
      'One-hour supply and demand zones decide where a trade may exist; a fifteen-minute rejection candle decides when. Target is 1R.',
  },
};

/** What each specific version changes or constrains. */
export const STRATEGY_CONDITIONS: Record<string, string> = {
  strategy_01_bill_williams_alligator_rrms:
    'Baseline Alligator and Heikin Ashi signal with RRMS sizing.',
  strategy_01_v2_bill_williams_alligator_rrms:
    'Second revision of the Alligator baseline.',
  strategy_01_v3_bill_williams_alligator_rrms:
    'Four-hour trend, one-hour entry, long only in a manually set bullish regime. Closes before the weekend.',
  strategy_01_v3_mgc_bill_williams_alligator_rrms:
    'The v3 rules on gold futures, with a contract multiplier and whole-contract sizing.',
  strategy_01_v3_weekend_bill_williams_alligator_rrms:
    'The v3 rules, but positions are held over the weekend instead of closed on Friday.',
  strategy_01_v4_multi_timeframe_alligator:
    'The one-hour, fifteen-minute and five-minute Alligator states must all agree before a fifteen-minute entry.',
  strategy_01_v5_dynamic_atr_jaw_buffer:
    'The stop buffer beyond the Jaw scales with ATR instead of using a fixed distance.',

  strategy_02_v1_5_multi_timeframe_alligator_zigzag:
    'One-hour Heikin Ashi crosses its Jaw against an open Alligator, with fifteen-minute Alligator alignment and a confirmed ZigZag level.',
  strategy_02_v2_vix_under_20:
    'Adds a regime filter: trade only while VIX is below 20.',
  strategy_02_v3_4h_trend_1h_execution_vix_under_20:
    'Four-hour trend with one-hour execution, restricted to VIX below 20.',

  strategy_03_v1_15m_alligator_open:
    'Enter when a completed fifteen-minute bar transitions into an open Alligator. No confirmation filters.',
  strategy_03_v1_1h_alligator_open:
    'Enter when a completed one-hour bar transitions into an open Alligator. No confirmation filters.',
  strategy_03_v1_4h_alligator_open:
    'Enter when a completed four-hour bar transitions into an open Alligator. No confirmation filters.',
  strategy_03_v1_4h_five_loss_capped_rrms:
    'Four-hour Alligator opening, with RRMS sizing capped after five consecutive losses.',
  strategy_03_v1_4h_weekly_reset_rrms:
    'Four-hour Alligator opening, with RRMS sizing reset at the start of each week.',

  strategy_04_v1_1h_zones_15m_reaction:
    'Qualified one-hour zones with a fifteen-minute rejection entry. No limit on how deep the trigger cuts into the zone.',
  strategy_04_v1_1_shallow_long_penetration:
    'Adds one rule to v1: a long trigger may cut no more than 25% into the demand zone.',
};

/** Leading `strategy_NN` of a compound strategy id, used to group the catalog. */
export function familyOf(strategyId: string): string {
  const match = /^(strategy_\d+)/.exec(strategyId);
  return match ? match[1] : strategyId;
}

/**
 * Orders strategy families newest first, so a future Strategy 05 appears at
 * the top rather than below everything that came before it.
 *
 * The comparison is numeric, not lexical: string ordering would put
 * `strategy_10` before `strategy_9` the moment the numbering passes nine.
 * Families whose id carries no number sort last.
 */
export function compareFamiliesNewestFirst(a: string, b: string): number {
  const numberOf = (family: string): number | null => {
    const match = /^strategy_(\d+)$/.exec(family);
    return match ? Number(match[1]) : null;
  };
  const left = numberOf(a);
  const right = numberOf(b);
  if (left !== null && right !== null) return right - left;
  if (left !== null) return -1;
  if (right !== null) return 1;
  return a.localeCompare(b);
}

export function familyInfo(strategyId: string): StrategyFamily {
  const key = familyOf(strategyId);
  return (
    STRATEGY_FAMILIES[key] ?? {
      label: key.replace(/_/g, ' '),
      summary: 'No description recorded for this strategy yet.',
    }
  );
}

/** Null rather than a placeholder, so callers can omit the line entirely. */
export function conditionsFor(strategyId: string): string | null {
  return STRATEGY_CONDITIONS[strategyId] ?? null;
}
