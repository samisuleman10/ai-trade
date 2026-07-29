export interface CatalogEntry {
  bundle_id: string;
  run: { run_id: string; strategy_id: string; strategy_version: string };
  instrument: { symbol: string };
  mode: string;
  generated_at: string;
  capabilities: Record<string, unknown>;
  dataset_ids: string[];
}

export interface HealthReport {
  status: string;
  valid_bundles: number;
  invalid_bundles: number;
}

/**
 * Where the catalog API lives. Set `VITE_API_BASE` to point the dashboard at
 * a server on another port or host; the default matches `python -m
 * ai_trade.server` run with no arguments.
 */
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8080';

async function getJson<T>(url: string, what: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${what} request failed: ${response.status}`);
  return response.json();
}

/**
 * Catalog and dataset responses are cached by URL for the life of the page.
 *
 * Both `Compare strategies` and `All runs` need the catalog plus one
 * performance dataset per run, so moving between the two sections repeated a
 * fan-out of roughly fifty requests every time. Bundles are immutable once
 * published -- a rerun writes a new manifest rather than editing one -- so
 * reusing a resolved response is safe. Rejections are evicted, so a failed
 * request can be retried rather than caching the failure forever.
 */
const cache = new Map<string, Promise<unknown>>();

function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  const hit = cache.get(key) as Promise<T> | undefined;
  if (hit) return hit;
  const pending = load().catch((error) => {
    cache.delete(key);
    throw error;
  });
  cache.set(key, pending);
  return pending;
}

/** Drop every cached response so the next call refetches. Used by the refresh control. */
export function clearCatalogCache(): void {
  cache.clear();
}

export async function fetchHealth(): Promise<HealthReport> {
  return getJson<HealthReport>(`${BASE}/health`, 'health');
}

export async function fetchRuns(filters: Record<string, string> = {}): Promise<CatalogEntry[]> {
  const query = new URLSearchParams(filters).toString();
  const url = `${BASE}/api/runs${query ? `?${query}` : ''}`;
  return cached(url, () => getJson<CatalogEntry[]>(url, 'catalog'));
}

export async function fetchDataset<T>(bundleId: string, datasetId: string): Promise<T> {
  const url = `${BASE}/api/runs/${encodeURIComponent(bundleId)}/datasets/${encodeURIComponent(datasetId)}`;
  return cached(url, () => getJson<T>(url, 'dataset'));
}
