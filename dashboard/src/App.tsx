import { useEffect, useState } from 'react';
import { BarChart3, Database, Layers3, RefreshCw } from 'lucide-react';
import { StrategyComparison } from './components/StrategyComparison';
import { RunCatalog } from './components/RunCatalog';
import { RunDetail } from './components/RunDetail';
import Strategy04Dashboard from './Strategy04Dashboard';
import type { CatalogEntry } from './catalog';

type Section = 'compare' | 'runs' | 'strategy04';

const SECTIONS: Array<{ id: Section; label: string; icon: typeof BarChart3 }> = [
  { id: 'compare', label: 'Compare strategies', icon: BarChart3 },
  { id: 'runs', label: 'All runs', icon: Database },
  { id: 'strategy04', label: 'Strategy 04', icon: Layers3 },
];

export default function App() {
  const [section, setSection] = useState<Section>('compare');
  const [selectedRun, setSelectedRun] = useState<CatalogEntry | null>(null);
  const [apiReachable, setApiReachable] = useState(false);
  const [checkingApi, setCheckingApi] = useState(false);

  const checkApi = async () => {
    setCheckingApi(true);
    try {
      const response = await fetch('http://localhost:8080/api/strategies');
      setApiReachable(response.ok);
    } catch {
      setApiReachable(false);
    } finally {
      setCheckingApi(false);
    }
  };

  useEffect(() => {
    void checkApi();
  }, []);

  const goToSection = (next: Section) => {
    setSection(next);
    // Navigating away from a run detail should always land back on that
    // section's list, not leave a stale detail view floating in a
    // section that didn't open it.
    setSelectedRun(null);
  };

  const footerLabel = selectedRun
    ? `${selectedRun.run.strategy_id} / ${selectedRun.run.strategy_version} / ${
        selectedRun.instrument.symbol || 'unknown symbol'
      }`
    : section === 'compare'
      ? 'cross-strategy comparison · ranked by average R'
      : section === 'runs'
        ? 'all discovered runs'
        : 'strategy_04 deep dive';

  return (
    <div className="s4-app min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-5 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <div className="s4-brand-mark">
              <Layers3 size={21} />
            </div>
            <div>
              <span className="s4-eyebrow">AI Trade Research</span>
              <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">
                AI Trade · Strategy Research Console
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className={`s4-api-status ${apiReachable ? 'online' : 'offline'}`}>
              <span />
              {apiReachable ? 'API reachable' : 'Saved result snapshot'}
            </div>
            <button
              type="button"
              className="s4-icon-button"
              aria-label="Check API connection"
              onClick={() => void checkApi()}
              disabled={checkingApi}
            >
              <RefreshCw size={15} className={checkingApi ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8">
        <nav className="s4-nav" aria-label="Top-level sections">
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-current={section === id ? 'page' : undefined}
              onClick={() => goToSection(id)}
              className={section === id ? 'is-active' : ''}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-5">
          {section === 'compare' &&
            (selectedRun ? (
              <RunDetail entry={selectedRun} onClose={() => setSelectedRun(null)} />
            ) : (
              <StrategyComparison onSelectRun={setSelectedRun} />
            ))}
          {section === 'runs' &&
            (selectedRun ? (
              <RunDetail entry={selectedRun} onClose={() => setSelectedRun(null)} />
            ) : (
              <RunCatalog onSelectRun={setSelectedRun} />
            ))}
          {section === 'strategy04' && <Strategy04Dashboard />}
        </div>

        <footer className="mt-8 flex flex-col gap-2 border-t border-slate-200 py-5 text-[11px] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Historical research only · no execution authority</span>
          <span className="font-mono">{footerLabel}</span>
        </footer>
      </main>
    </div>
  );
}
