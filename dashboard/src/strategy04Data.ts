export type Strategy04Version = 'v1' | 'v1_1';
export type Strategy04Asset = 'SPY' | 'QQQ' | 'DIA';
export type Strategy04Timeframe = '15m' | '1h';

export interface PerformanceMetrics {
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  netPnl: number;
  endingEquity: number;
  profitFactor: number;
  averageR: number;
  maxDrawdown: number;
  longTrades: number;
  shortTrades: number;
  maximumConsecutiveLosses: number;
  averageHoldingHours: number;
  totalCosts: number;
  maximumRrmsTier: number;
}

export interface DirectionMetrics {
  trades: number;
  wins: number;
  winRate: number;
}

export interface Strategy04Result {
  versionId: Strategy04Version;
  symbol: Strategy04Asset;
  startingEquity: number;
  candidateSignals: number;
  eligibleSignals: number;
  directionStats: { long: DirectionMetrics; short: DirectionMetrics };
  exitStats: { targets: number; stops: number; weekendExits: number };
  dataRange: { first: string; last: string };
  barCounts: { setup: number; execution: number };
  fixed: PerformanceMetrics;
  rrms: PerformanceMetrics;
}

export interface RuleGroup {
  title: string;
  subtitle: string;
  rules: string[];
}

export interface Strategy04Spec {
  versionId: Strategy04Version;
  title: string;
  hypothesis: string;
  changeFromPrior?: string;
  riskPolicy: string;
  ruleGroups: RuleGroup[];
}

// The per-run metric tables that used to live here were hand-transcribed
// from backtest reports. They are now read from each run's published
// run_summary dataset (see strategy04Summary.ts), so a rerun cannot leave
// the screen quoting the previous run. The types below stay: they are the
// shape that loader produces.

const sharedExecutionRules: RuleGroup[] = [
  {
    title: '1-hour zone engine',
    subtitle: 'Defines where a trade may exist.',
    rules: [
      'Only zones qualified before the 15-minute trigger bar opens are eligible.',
      'Demand zones support long setups; supply zones support short setups.',
      'Overlapping zones are ranked by evidence score, width, then stable zone ID.',
    ],
  },
  {
    title: 'Execution and exits',
    subtitle: 'Uses only completed information available at decision time.',
    rules: [
      'Enter at the next immediately following 15-minute bar open.',
      'Place the stop beyond the one-hour zone by 0.05 × the latest completed one-hour ATR(14).',
      'Target 1.0R. If stop and target occur in the same bar, assume the stop was hit first.',
    ],
  },
  {
    title: 'Session controls',
    subtitle: 'Locks the backtest to the approved US session.',
    rules: [
      'No entry before 10:30 America/New_York or from 15:00 onward.',
      'Friday entries are blocked.',
      'Open positions force-close in the final Friday 15-minute bar ending at 16:00.',
    ],
  },
];

export const STRATEGY_04_SPECS: Record<Strategy04Version, Strategy04Spec> = {
  v1: {
    versionId: 'v1',
    title: 'Strategy 04 v1.0 — Causal zone reaction',
    hypothesis:
      'Qualified one-hour supply and demand zones identify where a setup exists; a completed 15-minute rejection candle decides when the trade is allowed.',
    riskPolicy:
      'Compare a fixed 0.15% risk baseline with five-loss RRMS. RRMS changes position sizing only; entries and exits stay identical.',
    ruleGroups: [
      sharedExecutionRules[0],
      {
        title: '15-minute reaction',
        subtitle: 'Defines when the setup becomes executable.',
        rules: [
          'The trigger candle must contact the zone from its valid side.',
          'Long triggers close bullish above demand; short triggers close bearish below supply.',
          'One price reaction consumes its overlapping zones only once.',
        ],
      },
      ...sharedExecutionRules.slice(1),
    ],
  },
  v1_1: {
    versionId: 'v1_1',
    title: 'Strategy 04 v1.1 — Shallow long penetration',
    hypothesis:
      'The causal zone-reaction framework improves when long entries are rejected after price penetrates too deeply into a demand zone.',
    changeFromPrior:
      'Only the long trigger changes: the trigger low may penetrate no more than 25% of demand-zone width. Short entries and every other v1 rule remain unchanged.',
    riskPolicy:
      'Fixed risk uses 0.15% of current equity. RRMS uses 0.15%, 0.35%, 0.70%, 1.50%, and 1.50% tiers, resetting after profit or the fifth negative exit.',
    ruleGroups: [
      sharedExecutionRules[0],
      {
        title: '15-minute reaction',
        subtitle: 'Defines when the setup becomes executable.',
        rules: [
          'The trigger candle contacts the zone from its valid side and closes back outside it.',
          'Long triggers require a bullish close and no more than 25% demand-zone penetration.',
          'Short triggers require a bearish close below supply; v1 short logic is unchanged.',
          'One price reaction consumes its overlapping zones only once.',
        ],
      },
      ...sharedExecutionRules.slice(1),
    ],
  },
};

export const STRATEGY_04_VERSIONS: Array<{
  id: Strategy04Version;
  label: string;
  description: string;
}> = [
  {
    id: 'v1_1',
    label: 'v1.1',
    description: 'Shallow long penetration filter',
  },
  {
    id: 'v1',
    label: 'v1.0',
    description: 'Baseline causal zone reaction',
  },
];
