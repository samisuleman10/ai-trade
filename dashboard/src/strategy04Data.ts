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

const metrics = (
  trades: number,
  wins: number,
  losses: number,
  winRate: number,
  netPnl: number,
  endingEquity: number,
  profitFactor: number,
  averageR: number,
  maxDrawdown: number,
  longTrades: number,
  shortTrades: number,
  maximumConsecutiveLosses: number,
  averageHoldingHours: number,
  totalCosts: number,
  maximumRrmsTier: number,
): PerformanceMetrics => ({
  trades,
  wins,
  losses,
  winRate,
  netPnl,
  endingEquity,
  profitFactor,
  averageR,
  maxDrawdown,
  longTrades,
  shortTrades,
  maximumConsecutiveLosses,
  averageHoldingHours,
  totalCosts,
  maximumRrmsTier,
});

export const STRATEGY_04_RESULTS: Record<
  Strategy04Version,
  Record<Strategy04Asset, Strategy04Result>
> = {
  v1: {
    SPY: {
      versionId: 'v1',
      symbol: 'SPY',
      startingEquity: 100000,
      candidateSignals: 101,
      eligibleSignals: 44,
      directionStats: {
        long: { trades: 23, wins: 8, winRate: 0.34782608695652173 },
        short: { trades: 19, wins: 15, winRate: 0.7894736842105263 },
      },
      exitStats: { targets: 23, stops: 19, weekendExits: 0 },
      dataRange: { first: '2021-04-14T13:30:00Z', last: '2026-07-16T19:45:00Z' },
      barCounts: { setup: 9189, execution: 34200 },
      fixed: metrics(42, 23, 19, 0.547619, 308.971644, 100308.971644, 1.104725, 0.049811, 934.08341, 23, 19, 4, 3.928571, 46.13, 0),
      rrms: metrics(42, 23, 19, 0.547619, 1842.470423, 101842.470423, 1.26011, 0.049811, 2789.794753, 23, 19, 4, 3.928571, 110.84, 4),
    },
    QQQ: {
      versionId: 'v1',
      symbol: 'QQQ',
      startingEquity: 100000,
      candidateSignals: 121,
      eligibleSignals: 63,
      directionStats: {
        long: { trades: 30, wins: 18, winRate: 0.6 },
        short: { trades: 32, wins: 17, winRate: 0.53125 },
      },
      exitStats: { targets: 35, stops: 27, weekendExits: 0 },
      dataRange: { first: '2021-03-09T14:30:00Z', last: '2026-07-23T19:45:00Z' },
      barCounts: { setup: 10513, execution: 34980 },
      fixed: metrics(62, 35, 27, 0.564516, 893.016584, 100893.016584, 1.213788, 0.09743, 1096.65001, 30, 32, 7, 6.25, 56.79, 0),
      rrms: metrics(62, 35, 27, 0.564516, 1320.586272, 101320.586272, 1.142217, 0.09743, 4960.693734, 30, 32, 7, 6.25, 123.68, 4),
    },
    DIA: {
      versionId: 'v1',
      symbol: 'DIA',
      startingEquity: 100000,
      candidateSignals: 110,
      eligibleSignals: 53,
      directionStats: {
        long: { trades: 27, wins: 12, winRate: 0.4444444444444444 },
        short: { trades: 26, wins: 17, winRate: 0.6538461538461539 },
      },
      exitStats: { targets: 29, stops: 24, weekendExits: 0 },
      dataRange: { first: '2021-03-09T14:30:00Z', last: '2026-07-23T19:45:00Z' },
      barCounts: { setup: 10513, execution: 34980 },
      fixed: metrics(53, 29, 24, 0.54717, 349.504333, 100349.504333, 1.092372, 0.045215, 759.274159, 27, 26, 4, 6.264151, 82, 0),
      rrms: metrics(53, 29, 24, 0.54717, -360.060531, 99639.939469, 0.96732, 0.045215, 3570.087775, 27, 26, 4, 6.264151, 210.01, 4),
    },
  },
  v1_1: {
    SPY: {
      versionId: 'v1_1',
      symbol: 'SPY',
      startingEquity: 100000,
      candidateSignals: 93,
      eligibleSignals: 39,
      directionStats: {
        long: { trades: 16, wins: 8, winRate: 0.5 },
        short: { trades: 22, wins: 16, winRate: 0.7272727272727273 },
      },
      exitStats: { targets: 24, stops: 14, weekendExits: 0 },
      dataRange: { first: '2021-04-14T13:30:00Z', last: '2026-07-16T19:45:00Z' },
      barCounts: { setup: 9189, execution: 34200 },
      fixed: metrics(38, 24, 14, 0.631579, 1244.915543, 101244.915543, 1.570183, 0.218363, 633.436915, 16, 22, 3, 4.796053, 41.83, 0),
      rrms: metrics(38, 24, 14, 0.631579, 3626.286724, 103626.286724, 2.065507, 0.218363, 1231.026652, 16, 22, 3, 4.796053, 68.03, 3),
    },
    QQQ: {
      versionId: 'v1_1',
      symbol: 'QQQ',
      startingEquity: 100000,
      candidateSignals: 113,
      eligibleSignals: 60,
      directionStats: {
        long: { trades: 24, wins: 13, winRate: 0.5416666666666666 },
        short: { trades: 35, wins: 18, winRate: 0.5142857142857142 },
      },
      exitStats: { targets: 31, stops: 28, weekendExits: 0 },
      dataRange: { first: '2021-03-09T14:30:00Z', last: '2026-07-23T19:45:00Z' },
      barCounts: { setup: 10513, execution: 34980 },
      fixed: metrics(59, 31, 28, 0.525424, 163.059177, 100163.059177, 1.037727, 0.019032, 1387.659188, 24, 35, 9, 6.444915, 54.81, 0),
      rrms: metrics(59, 31, 28, 0.525424, -993.825992, 99006.174008, 0.915865, 0.019032, 7234.136005, 24, 35, 9, 6.444915, 143.05, 4),
    },
    DIA: {
      versionId: 'v1_1',
      symbol: 'DIA',
      startingEquity: 100000,
      candidateSignals: 95,
      eligibleSignals: 49,
      directionStats: {
        long: { trades: 22, wins: 12, winRate: 0.5454545454545454 },
        short: { trades: 27, wins: 18, winRate: 0.6666666666666666 },
      },
      exitStats: { targets: 30, stops: 19, weekendExits: 0 },
      dataRange: { first: '2021-03-09T14:30:00Z', last: '2026-07-23T19:45:00Z' },
      barCounts: { setup: 10513, execution: 34980 },
      fixed: metrics(49, 30, 19, 0.612245, 1295.225184, 101295.225184, 1.429645, 0.176998, 528.885228, 22, 27, 3, 6.377551, 73.66, 0),
      rrms: metrics(49, 30, 19, 0.612245, 4468.490864, 104468.490864, 1.841996, 0.176998, 1292.787314, 22, 27, 3, 6.377551, 143.33, 3),
    },
  },
};

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
