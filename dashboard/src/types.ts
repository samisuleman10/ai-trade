export type StrategyId = 'strategy_04' | 'strategy_01' | 'strategy_02' | 'strategy_03';
export type Timeframe = '15m' | '1h' | '4h';

export interface ResearchProfile {
  id: string;
  name: string;
  symbol: string;
  assetClass: 'ETF' | 'Futures';
  description: string;
  lastUpdated: string;
}

export interface StrategyVersion {
  id: string;
  name: string;
  description: string;
  assets: string[];
  isPlanned?: boolean;
}

export interface StrategyDefinition {
  id: StrategyId;
  name: string;
  code: string;
  description: string;
  defaultVersion: string;
  versions: StrategyVersion[];
}

export interface Bar {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  jaw?: number;   // Alligator Jaw (Blue)
  teeth?: number; // Alligator Teeth (Red)
  lips?: number;  // Alligator Lips (Green)
  haOpen?: number;
  haHigh?: number;
  haLow?: number;
  haClose?: number;
}

export type TradeSide = 'long' | 'short';
export type ExitReason = 'stop' | 'target' | 'weekend_close' | 'manual';

export interface Trade {
  id: string;
  number: number;
  decisionTimestamp: string;
  entryTimestamp: string;
  exitTimestamp: string;
  side: TradeSide;
  rrmsTier: number;
  quantity: number;
  entryPrice: number;
  stopPrice: number;
  targetPrice: number;
  exitPrice: number;
  exitReason: ExitReason;
  grossPnl: number;
  costs: number;
  netPnl: number;
  resultR: number;
  equityAfter: number;
}

export interface StrategySummary {
  strategyId: string;
  versionId: string;
  name: string;
  symbol: string;
  timeframe: string;
  startingEquity: number;
  endingEquityFixed: number;
  endingEquityRrms: number;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  netPnlFixed: number;
  netPnlRrms: number;
  profitFactorFixed: number;
  profitFactorRrms: number;
  maxDrawdownFixed: number;
  maxDrawdownRrms: number;
  avgR: number;
  description: string;
}

export interface StrategySpec {
  strategyId: StrategyId;
  versionId: string;
  title: string;
  markdownContent: string;
  indicatorRules: Array<{ name: string; font?: string; rule: string }>;
  riskPolicy: string;
}

export interface VisualRender {
  id: string;
  title: string;
  description: string;
  category: 'trade_review' | 'zone_review' | 'loss_diagnostic';
  svgContent: string;
}

export interface ShadowState {
  status: 'active' | 'idle' | 'closed';
  currentSession: string;
  nyWindowOpen: boolean;
  activeIntent?: {
    symbol: string;
    side: TradeSide;
    entryPrice: number;
    stopPrice: number;
    targetPrice: number;
    entryTime: string;
    unrealizedPnl: number;
  };
  recentDecisions: Array<{
    timestamp: string;
    decision: 'signal_accepted' | 'no_signal' | 'window_closed';
    reason: string;
  }>;
}
