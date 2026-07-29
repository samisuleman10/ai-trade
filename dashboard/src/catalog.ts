export interface CatalogEntry {
  bundle_id: string;
  run: { run_id: string; strategy_id: string; strategy_version: string };
  instrument: { symbol: string };
  mode: string;
  generated_at: string;
  capabilities: Record<string, unknown>;
  dataset_ids: string[];
}

const BASE = 'http://localhost:8080';

export async function fetchRuns(filters: Record<string, string> = {}): Promise<CatalogEntry[]> {
  const query = new URLSearchParams(filters).toString();
  const response = await fetch(`${BASE}/api/runs${query ? `?${query}` : ''}`);
  if (!response.ok) throw new Error(`catalog request failed: ${response.status}`);
  return response.json();
}

export async function fetchDataset<T>(bundleId: string, datasetId: string): Promise<T> {
  const response = await fetch(`${BASE}/api/runs/${encodeURIComponent(bundleId)}/datasets/${encodeURIComponent(datasetId)}`);
  if (!response.ok) throw new Error(`dataset request failed: ${response.status}`);
  return response.json();
}
