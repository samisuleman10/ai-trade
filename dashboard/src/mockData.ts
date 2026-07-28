import type {
  Bar,
  ShadowState,
  StrategyDefinition,
  StrategyId,
  StrategySpec,
  StrategySummary,
  Trade,
  VisualRender,
} from './types';

// Strategies in Descending Order: Strategy 04, Strategy 03, Strategy 02, Strategy 01
export const STRATEGIES: StrategyDefinition[] = [
  {
    id: 'strategy_04',
    name: 'Strategy 04 (Supply & Demand)',
    code: 'S4',
    description: 'Institutional Supply & Demand zone reaction strategy with ATR channels and RRMS scaling.',
    defaultVersion: 'v1_1',
    // Descending version order (Newest version first)
    versions: [
      { id: 'v3', name: 'v3.0 (Planned)', description: 'Orderbook footprint & liquidity sweep integration.', assets: ['SPY'], isPlanned: true },
      { id: 'v2', name: 'v2.0 (Planned)', description: 'Multi-zone confirmation with volume profile.', assets: ['SPY'], isPlanned: true },
      { id: 'v1_1', name: 'v1.1 RRMS Risk Filtered', description: 'RRMS 5-loss reset and weekend forced close.', assets: ['SPY', 'QQQ', 'DIA', 'MGC'] },
      { id: 'v1', name: 'v1.0 Baseline Zone Entry', description: 'Initial Supply/Demand zone bounce logic.', assets: ['SPY', 'QQQ'] },
    ],
  },
  {
    id: 'strategy_03',
    name: 'Strategy 03 (Volatility Reset)',
    code: 'S3',
    description: 'ATR volatility reset & 5-loss RRMS reset profile.',
    defaultVersion: 'v1',
    versions: [
      { id: 'v1', name: 'v1.0 4H Weekly Reset', description: 'Weekly risk reset baseline.', assets: ['SPY'] },
    ],
  },
  {
    id: 'strategy_02',
    name: 'Strategy 02 (Intraday Momentum)',
    code: 'S2',
    description: 'EMA cross & ATR breakout intraday strategy.',
    defaultVersion: 'v1_5',
    versions: [
      { id: 'v1_5', name: 'v1.5 ATR Breakout Baseline', description: 'Intraday momentum breakout profile.', assets: ['SPY', 'QQQ'] },
    ],
  },
  {
    id: 'strategy_01',
    name: 'Strategy 01 (Bill Williams Alligator)',
    code: 'S1',
    description: 'Alligator Jaw/Teeth/Lips expansion with Heikin Ashi confirmation and 4H macro filter.',
    defaultVersion: 'v3',
    versions: [
      { id: 'v4', name: 'v4.0 Multi-Timeframe Alignment', description: 'Resumable multi-timeframe cache alignment.', assets: ['SPY'] },
      { id: 'v3', name: 'v3.0 4H Confirmation / 1H Entry', description: 'Bullish macro regime with 4H confirmation and weekend forced close.', assets: ['SPY', 'MGC', 'QQQ', 'DIA'] },
      { id: 'v2', name: 'v2.0 Diagnostic Report Profile', description: 'Candidate signal reporting profile.', assets: ['SPY'] },
      { id: 'v1', name: 'v1.0 Single Timeframe Diagnostic', description: 'Read-only regular hours diagnostic.', assets: ['SPY'] },
    ],
  },
];

export const STRATEGY_SPECS: Record<StrategyId, Record<string, StrategySpec>> = {
  strategy_04: {
    v1_1: {
      strategyId: 'strategy_04',
      versionId: 'v1_1',
      title: 'Strategy 04 v1.1 - Supply & Demand Zone Reaction',
      markdownContent: `# Strategy 04 v1.1 Specification

## 1. Objective & Hypothesis
Strategy 04 identifies **institutional Supply & Demand imbalances** formed by strong impulse moves. The strategy enters when price retraces into a fresh, unmitigated zone during regular trading hours.

## 2. Indicator & Zone Rules
- **Zone Identification**: Base candles with tight range (< 0.5 ATR) followed by an explosive leg-out (> 2.0 ATR).
- **Zone Validity**: Zone is considered fresh until price pierces through 50% of the zone thickness.
- **Entry Trigger**: Limit or market entry upon retest of the zone boundary during NY regular trading hours.

## 3. Exit & Risk Rules
- **Stop Loss**: Placed 0.2 ATR beyond the distal zone edge.
- **Take Profit**: Targeted at 1.5R to 2.0R distance or opposite supply/demand zone.
- **RRMS Risk Scaling**: Baseline risk 0.15% of equity per trade. Tier advances after 2 consecutive wins; resets after 5 losses or weekly boundary.
`,
      indicatorRules: [
        { name: 'Supply Zone', rule: 'Resistance area where aggressive selling occurred.' },
        { name: 'Demand Zone', rule: 'Support area where aggressive buying occurred.' },
        { name: 'ATR Filter', rule: 'Requires minimum 2.0x ATR expansion on leg-out.' },
      ],
      riskPolicy: 'Fixed 0.15% per trade with RRMS progressive tier scaling and weekend force-close.',
    },
    v1: {
      strategyId: 'strategy_04',
      versionId: 'v1',
      title: 'Strategy 04 v1.0 - Baseline Zone Entry',
      markdownContent: `# Strategy 04 v1.0 Specification\n\nInitial baseline strategy testing raw Supply/Demand zone bounces without RRMS risk filters.`,
      indicatorRules: [
        { name: 'Supply Zone', rule: 'Base + Leg Out' },
        { name: 'Demand Zone', rule: 'Base + Leg Out' },
      ],
      riskPolicy: 'Fixed 0.15% per trade without tier progression.',
    },
  },
  strategy_01: {
    v3: {
      strategyId: 'strategy_01',
      versionId: 'v3',
      title: 'Strategy 01 v3 - Bill Williams Alligator (4H Confirmation)',
      markdownContent: `# Strategy 01 v3 Specification\n\n## Rules\n1. Completed 4H Alligator state must confirm bullish trend.\n2. Entry on completed 1H bar lip expansion.\n3. Weekend forced close on Friday 15:45 NY bar.`,
      indicatorRules: [
        { name: 'Jaw (13)', rule: '13-period SMMA shifted 8 bars' },
        { name: 'Teeth (8)', rule: '8-period SMMA shifted 5 bars' },
        { name: 'Lips (5)', rule: '5-period SMMA shifted 3 bars' },
      ],
      riskPolicy: 'RRMS progressive risk tiers with Friday forced exit.',
    },
  },
  strategy_02: {
    v1_5: {
      strategyId: 'strategy_02',
      versionId: 'v1_5',
      title: 'Strategy 02 v1.5 - Intraday Momentum',
      markdownContent: `# Strategy 02 v1.5 Specification\n\nIntraday momentum breakout strategy based on EMA 9/21 cross.`,
      indicatorRules: [{ name: 'EMA Cross', rule: 'Cross in direction of 1H trend' }],
      riskPolicy: 'Fixed 0.20% per trade.',
    },
  },
  strategy_03: {
    v1: {
      strategyId: 'strategy_03',
      versionId: 'v1',
      title: 'Strategy 03 v1.0 - Volatility Reset',
      markdownContent: `# Strategy 03 v1.0 Specification\n\nIntraday ATR volatility reset model.`,
      indicatorRules: [{ name: 'ATR Reset', rule: 'Reset risk on 5 loss streak' }],
      riskPolicy: 'Weekly risk reset policy.',
    },
  },
};

export const MOCK_SUMMARY_S4_SPY: StrategySummary = {
  strategyId: 'strategy_04',
  versionId: 'v1_1',
  name: 'Strategy 04 v1.1 (Supply & Demand)',
  symbol: 'SPY',
  timeframe: '1h',
  startingEquity: 100000.0,
  endingEquityFixed: 101850.40,
  endingEquityRrms: 104210.80,
  totalTrades: 24,
  wins: 14,
  losses: 10,
  winRate: 0.583,
  netPnlFixed: 1850.40,
  netPnlRrms: 4210.80,
  profitFactorFixed: 1.482,
  profitFactorRrms: 1.895,
  maxDrawdownFixed: 420.50,
  maxDrawdownRrms: 890.30,
  avgR: 0.425,
  description: 'Supply & Demand zone bounce with RRMS progressive risk scaling.',
};

export const MOCK_TRADES_S4: Trade[] = [
  {
    id: 's4-1',
    number: 1,
    decisionTimestamp: '2026-05-04T14:30:00Z',
    entryTimestamp: '2026-05-04T14:30:00Z',
    exitTimestamp: '2026-05-04T18:00:00Z',
    side: 'long',
    rrmsTier: 0,
    quantity: 65,
    entryPrice: 718.50,
    stopPrice: 715.20,
    targetPrice: 723.45,
    exitPrice: 723.40,
    exitReason: 'target',
    grossPnl: 318.50,
    costs: 0.65,
    netPnl: 317.85,
    resultR: 1.48,
    equityAfter: 100317.85,
  },
  {
    id: 's4-2',
    number: 2,
    decisionTimestamp: '2026-05-07T15:00:00Z',
    entryTimestamp: '2026-05-07T15:00:00Z',
    exitTimestamp: '2026-05-07T19:30:00Z',
    side: 'short',
    rrmsTier: 1,
    quantity: 72,
    entryPrice: 728.40,
    stopPrice: 731.80,
    targetPrice: 723.30,
    exitPrice: 723.25,
    exitReason: 'target',
    grossPnl: 370.80,
    costs: 0.72,
    netPnl: 370.08,
    resultR: 1.51,
    equityAfter: 100687.93,
  },
  {
    id: 's4-3',
    number: 3,
    decisionTimestamp: '2026-05-12T16:15:00Z',
    entryTimestamp: '2026-05-12T16:15:00Z',
    exitTimestamp: '2026-05-13T13:30:00Z',
    side: 'long',
    rrmsTier: 2,
    quantity: 80,
    entryPrice: 721.10,
    stopPrice: 718.40,
    targetPrice: 725.15,
    exitPrice: 718.30,
    exitReason: 'stop',
    grossPnl: -224.00,
    costs: 0.80,
    netPnl: -224.80,
    resultR: -1.03,
    equityAfter: 100463.13,
  },
];

export const MOCK_VISUALS_S4: VisualRender[] = [
  {
    id: 's4_trade_review',
    title: 'Strategy 04 Trade Execution Review (Trades #1-#24)',
    description: 'Deterministic candlestick renders displaying demand zone entries, stop levels, and target fills.',
    category: 'trade_review',
    svgContent: `<svg viewBox="0 0 800 240" xmlns="http://www.w3.org/2000/svg" style="background:#090d16; border-radius:8px;">
      <text x="20" y="35" fill="#f8fafc" font-size="14" font-weight="bold">Strategy 04 Trade Review Matrix</text>
      <rect x="40" y="60" width="720" height="150" fill="#0d121d" rx="6" stroke="rgba(255,255,255,0.08)"/>
      <line x1="60" y1="180" x2="740" y2="180" stroke="#334155"/>
      <rect x="120" y="100" width="18" height="60" fill="#10b981" rx="2"/>
      <line x1="129" y1="80" x2="129" y2="175" stroke="#10b981" stroke-width="2"/>
      <rect x="220" y="90" width="18" height="75" fill="#ef4444" rx="2"/>
      <line x1="229" y1="75" x2="229" y2="180" stroke="#ef4444" stroke-width="2"/>
      <rect x="320" y="85" width="18" height="80" fill="#10b981" rx="2"/>
      <line x1="329" y1="70" x2="329" y2="175" stroke="#10b981" stroke-width="2"/>
      <text x="120" y="200" fill="#94a3b8" font-size="11" font-family="monospace">Trade #1 (+1.48R)</text>
      <text x="220" y="200" fill="#94a3b8" font-size="11" font-family="monospace">Trade #2 (-1.03R)</text>
      <text x="320" y="200" fill="#94a3b8" font-size="11" font-family="monospace">Trade #3 (+1.51R)</text>
    </svg>`,
  },
  {
    id: 's4_zone_review',
    title: 'Supply & Demand Zone Formation Analysis',
    description: 'Identified consolidation base candles and strong impulse leg-out validation.',
    category: 'zone_review',
    svgContent: `<svg viewBox="0 0 800 240" xmlns="http://www.w3.org/2000/svg" style="background:#090d16; border-radius:8px;">
      <text x="20" y="35" fill="#6366f1" font-size="14" font-weight="bold">Supply & Demand Zone Formation</text>
      <rect x="60" y="90" width="220" height="50" fill="rgba(16,185,129,0.15)" stroke="#10b981" stroke-dasharray="4" rx="4"/>
      <text x="75" y="120" fill="#34d399" font-size="12" font-weight="bold">Fresh Demand Zone ($718.50 - $721.10)</text>
      <path d="M 300 140 L 420 70 L 520 115 L 680 50" fill="none" stroke="#6366f1" stroke-width="3"/>
      <circle cx="520" cy="115" r="6" fill="#10b981"/>
      <text x="535" y="120" fill="#f8fafc" font-size="11">Zone Retest Entry</text>
    </svg>`,
  },
  {
    id: 's4_loss_diagnostic',
    title: 'Long Losses Diagnostic & Intrabar Collision Analysis',
    description: 'Breakdown of 10 loss trades evaluated against ATR volatility and Friday forced exits.',
    category: 'loss_diagnostic',
    svgContent: `<svg viewBox="0 0 800 240" xmlns="http://www.w3.org/2000/svg" style="background:#090d16; border-radius:8px;">
      <text x="20" y="35" fill="#f43f5e" font-size="14" font-weight="bold">Loss Diagnostic Breakdown</text>
      <rect x="60" y="70" width="180" height="120" fill="#0d121d" rx="6" stroke="rgba(255,255,255,0.08)"/>
      <text x="80" y="100" fill="#f43f5e" font-size="20" font-weight="bold">6 Stop Exits</text>
      <text x="80" y="130" fill="#f59e0b" font-size="16" font-weight="bold">4 Weekend Closes</text>
      <text x="80" y="160" fill="#94a3b8" font-size="11">Avg Loss Depth: -1.02R</text>
    </svg>`,
  },
];

export function generateMockBars(): Bar[] {
  const bars: Bar[] = [];
  const startTimestamp = Math.floor(new Date('2026-05-01T13:30:00Z').getTime() / 1000);
  let price = 715.0;

  for (let i = 0; i < 200; i++) {
    const time = startTimestamp + i * 3600;
    const change = (Math.sin(i / 5) * 1.8) + ((Math.random() - 0.47) * 2.4);
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 1.5;
    const low = Math.min(open, close) - Math.random() * 1.5;

    bars.push({
      time,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      jaw: parseFloat((price - Math.sin(i / 8) * 2.0).toFixed(2)),
      teeth: parseFloat((price - Math.sin(i / 6) * 1.4).toFixed(2)),
      lips: parseFloat((price - Math.sin(i / 4) * 0.8).toFixed(2)),
    });

    price = close;
  }

  return bars;
}

export const MOCK_SHADOW_STATE: ShadowState = {
  status: 'active',
  currentSession: 'Regular Trading Hours (NY)',
  nyWindowOpen: true,
  activeIntent: {
    symbol: 'SPY',
    side: 'long',
    entryPrice: 721.10,
    stopPrice: 718.40,
    targetPrice: 725.15,
    entryTime: '2026-07-28T14:30:00Z',
    unrealizedPnl: +195.20,
  },
  recentDecisions: [
    {
      timestamp: '2026-07-28T14:30:00Z',
      decision: 'signal_accepted',
      reason: 'Fresh Demand Zone retest confirmed + 1H impulse candle expansion.',
    },
    {
      timestamp: '2026-07-27T18:45:00Z',
      decision: 'no_signal',
      reason: 'Zone already mitigated (>50% penetration).',
    },
  ],
};
