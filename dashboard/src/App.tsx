import { useEffect, useState } from 'react';
import type { Bar, ShadowState, StrategyId, StrategySpec, StrategySummary, Timeframe, Trade, VisualRender } from './types';
import {
  generateMockBars,
  MOCK_SHADOW_STATE,
  MOCK_SUMMARY_S4_SPY,
  MOCK_TRADES_S4,
  MOCK_VISUALS_S4,
  STRATEGIES,
  STRATEGY_SPECS,
} from './mockData';
import { Header } from './components/Header';
import { StrategySelector } from './components/StrategySelector';
import { StrategySpecView } from './components/StrategySpecView';
import { KpiSummary } from './components/KpiSummary';
import { CandlestickChart } from './components/CandlestickChart';
import { EquityChart } from './components/EquityChart';
import { TradeTable } from './components/TradeTable';
import { VisualGallery } from './components/VisualGallery';
import { ShadowTradingPanel } from './components/ShadowTradingPanel';
import { BarChart3, BookOpen, Layers, Image as ImageIcon, Zap } from 'lucide-react';

export function App() {
  // Strategy Hierarchy State
  const [selectedStrategyId, setSelectedStrategyId] = useState<StrategyId>('strategy_04');
  const [selectedVersionId, setSelectedVersionId] = useState<string>('v1_1');
  const [selectedAsset, setSelectedAsset] = useState<string>('SPY');

  // Main Section View Tabs
  const [activeSection, setActiveSection] = useState<'spec' | 'backtest' | 'chart' | 'visuals' | 'shadow'>('spec');

  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>('1h');
  const [useRrms, setUseRrms] = useState<boolean>(true);
  const [focusedTrade, setFocusedTrade] = useState<Trade | null>(null);

  // Strategy Data State
  const currentStrategyDef = STRATEGIES.find((s) => s.id === selectedStrategyId) || STRATEGIES[0];
  const currentVersionDef = currentStrategyDef.versions.find((v) => v.id === selectedVersionId) || currentStrategyDef.versions[0];
  const currentSpec: StrategySpec = STRATEGY_SPECS[selectedStrategyId]?.[selectedVersionId] || STRATEGY_SPECS.strategy_04.v1_1;

  const [summary, setSummary] = useState<StrategySummary>(MOCK_SUMMARY_S4_SPY);
  const [trades, setTrades] = useState<Trade[]>(MOCK_TRADES_S4);
  const [bars] = useState<Bar[]>(generateMockBars());
  const [visuals] = useState<VisualRender[]>(MOCK_VISUALS_S4);
  const [shadowState] = useState<ShadowState>(MOCK_SHADOW_STATE);

  const [isBackendConnected, setIsBackendConnected] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Fetch strategy data from backend API if available
  const fetchData = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`http://localhost:8080/api/strategy/backtest?strategy=${selectedStrategyId}&version=${selectedVersionId}&asset=${selectedAsset}`);
      if (res.ok) {
        const data = await res.json();
        if (data.summary) setSummary(data.summary);
        if (data.trades) setTrades(data.trades);
        setIsBackendConnected(true);
      } else {
        setIsBackendConnected(false);
      }
    } catch {
      setIsBackendConnected(false);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedStrategyId, selectedVersionId, selectedAsset]);

  const handleFocusTrade = (trade: Trade) => {
    setFocusedTrade(trade);
    setActiveSection('chart'); // Auto switch to chart view on focus
  };

  return (
    <div className="min-h-screen bg-[#f1f5f9] text-slate-900 p-4 md:p-6 max-w-[1600px] mx-auto">
      {/* ROW 1: Header with Brand Title, Strategy Context Text Summary, API Status */}
      <Header
        strategyName={currentStrategyDef.name}
        versionName={currentVersionDef.name}
        selectedAsset={selectedAsset}
        riskPolicy={currentSpec.riskPolicy}
        isBackendConnected={isBackendConnected}
        onRefresh={fetchData}
        isRefreshing={isRefreshing}
      />

      {/* ROW 2 & ROW 3: Primary Strategy Picker (Row 2) + Version Iteration & Target Asset (Row 3) */}
      <StrategySelector
        strategies={STRATEGIES}
        selectedStrategyId={selectedStrategyId}
        onSelectStrategy={(id) => {
          setSelectedStrategyId(id);
          const strat = STRATEGIES.find((s) => s.id === id);
          if (strat) {
            setSelectedVersionId(strat.defaultVersion);
            setSelectedAsset(strat.versions[0]?.assets[0] || 'SPY');
          }
        }}
        selectedVersionId={selectedVersionId}
        onSelectVersion={setSelectedVersionId}
        selectedAsset={selectedAsset}
        onSelectAsset={setSelectedAsset}
      />

      {/* ROW 4: Navigation Section Tabs */}
      <div className="flex items-center gap-2 mb-6 border-b border-slate-300 pb-3 flex-wrap">
        <button
          onClick={() => setActiveSection('spec')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
            activeSection === 'spec'
              ? 'bg-indigo-600 text-white shadow-xs font-bold'
              : 'bg-[#f8fafc] text-slate-800 hover:bg-slate-200 border border-slate-200'
          }`}
        >
          <BookOpen className="w-4 h-4 text-indigo-700" />
          📜 Strategy Specification & Rules
        </button>

        <button
          onClick={() => setActiveSection('backtest')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
            activeSection === 'backtest'
              ? 'bg-indigo-600 text-white shadow-xs font-bold'
              : 'bg-[#f8fafc] text-slate-800 hover:bg-slate-200 border border-slate-200'
          }`}
        >
          <Layers className="w-4 h-4 text-sky-700" />
          📊 Asset Backtest Performance
        </button>

        <button
          onClick={() => setActiveSection('chart')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
            activeSection === 'chart'
              ? 'bg-indigo-600 text-white shadow-xs font-bold'
              : 'bg-[#f8fafc] text-slate-800 hover:bg-slate-200 border border-slate-200'
          }`}
        >
          <BarChart3 className="w-4 h-4 text-emerald-700" />
          📈 Interactive Chart & Equity Engine
        </button>

        <button
          onClick={() => setActiveSection('visuals')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
            activeSection === 'visuals'
              ? 'bg-indigo-600 text-white shadow-xs font-bold'
              : 'bg-[#f8fafc] text-slate-800 hover:bg-slate-200 border border-slate-200'
          }`}
        >
          <ImageIcon className="w-4 h-4 text-amber-700" />
          🖼️ Stored Visual Renders Gallery ({visuals.length})
        </button>

        <button
          onClick={() => setActiveSection('shadow')}
          className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
            activeSection === 'shadow'
              ? 'bg-indigo-600 text-white shadow-xs font-bold'
              : 'bg-[#f8fafc] text-slate-800 hover:bg-slate-200 border border-slate-200'
          }`}
        >
          <Zap className="w-4 h-4 text-amber-700" />
          ⚡ Shadow Gateway
        </button>
      </div>

      {/* SECTION 1: Rules & Specification */}
      {activeSection === 'spec' && <StrategySpecView spec={currentSpec} />}

      {/* SECTION 2: Asset Backtest Results */}
      {activeSection === 'backtest' && (
        <div className="space-y-6">
          <KpiSummary summary={summary} useRrms={useRrms} onToggleRrms={setUseRrms} />

          <TradeTable
            trades={trades}
            focusedTradeId={focusedTrade?.id}
            onFocusTrade={handleFocusTrade}
          />
        </div>
      )}

      {/* SECTION 3: Interactive Chart & Equity Curves */}
      {activeSection === 'chart' && (
        <div className="space-y-6">
          <KpiSummary summary={summary} useRrms={useRrms} onToggleRrms={setUseRrms} />

          <CandlestickChart
            bars={bars}
            trades={trades}
            focusedTrade={focusedTrade}
            selectedTimeframe={selectedTimeframe}
            onSelectTimeframe={setSelectedTimeframe}
          />
          <EquityChart summary={summary} trades={trades} />
        </div>
      )}

      {/* SECTION 4: Stored Visual Graph Gallery */}
      {activeSection === 'visuals' && <VisualGallery visuals={visuals} />}

      {/* SECTION 5: Shadow Trading Panel */}
      {activeSection === 'shadow' && <ShadowTradingPanel shadowState={shadowState} />}

      {/* Footer */}
      <footer className="mt-8 pt-4 border-t border-slate-300 text-center text-xs text-slate-600 flex justify-between items-center font-mono">
        <div>AI Trade Strategy Hub • Institutional Architecture</div>
        <div>Active: {currentStrategyDef.name} ({currentVersionDef.name})</div>
      </footer>
    </div>
  );
}

export default App;
