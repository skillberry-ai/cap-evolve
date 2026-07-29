/** Typed wrappers over the cap-evolve dashboard backend (/api/*).
 *
 * Two modes:
 *  - LIVE (default): fetch from the FastAPI backend at /api/*.
 *  - STATIC: when built with VITE_STATIC=1 or when `window.__CAPEVOLVE_STATIC__`
 *    is truthy at runtime, every request is served from pre-generated JSON files
 *    under `./data/` (a deterministic slug of the path+query). No backend, no SSE.
 *    Used by the self-contained static export (examples/.../ui/).
 */
import type {
  CandidateDiff,
  CandidateFile,
  CompareResult,
  FileResult,
  GitCommit,
  GitDiffResult,
  MemoryResult,
  RolloutDetail,
  RolloutRow,
  RunDetail,
  RunSummary,
  TreeResult,
} from './types'

/** True when the SPA must serve everything from static ./data/*.json (no backend). */
export const STATIC_MODE: boolean =
  (typeof import.meta !== 'undefined' &&
    (import.meta as { env?: Record<string, unknown> }).env?.VITE_STATIC === '1') ||
  (typeof window !== 'undefined' &&
    Boolean((window as unknown as { __CAPEVOLVE_STATIC__?: unknown }).__CAPEVOLVE_STATIC__))

/** Slugify an /api/* path+query into a flat, deterministic filename (no extension).
 *
 * Must match the Python exporter's slug() exactly: lowercase, every run of
 * non-alphanumeric chars collapsed to a single '_', leading/trailing '_' trimmed.
 * The leading `/api/` prefix is dropped first so `/api/runs` -> `runs`.
 */
export function staticSlug(url: string): string {
  const path = url.replace(/^\/api\/?/, '')
  const slug = path
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return slug || 'index'
}

/** Base for the static data dir. Read lazily (not a module-level const) — main.tsx sets
 * window.__CAPEVOLVE_DATA_BASE__ *after* this module has already been evaluated, so a
 * top-level const would capture the default before the override lands. Relative default
 * so it still works from any subpath/host when there is no override. */
function dataBase(): string {
  const override = (window as unknown as { __CAPEVOLVE_DATA_BASE__?: string })
    .__CAPEVOLVE_DATA_BASE__
  return override || 'data'
}

/** Reads a `?dataBase=` query param and, if present, sets window.__CAPEVOLVE_DATA_BASE__
 * so getJSON() serves static requests from that (absolute) URL instead of the relative
 * default. Called once by main.tsx before mounting. */
export function applyDataBaseOverride(search: string = window.location.search): void {
  const override = new URLSearchParams(search).get('dataBase')
  if (override) {
    (window as unknown as { __CAPEVOLVE_DATA_BASE__?: string }).__CAPEVOLVE_DATA_BASE__ = override
  }
}

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const target = STATIC_MODE ? `${dataBase()}/${staticSlug(url)}.json` : url
  const res = await fetch(target, { signal })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${target}`)
  }
  return (await res.json()) as T
}

export const api = {
  runs: (signal?: AbortSignal) => getJSON<RunSummary[]>('/api/runs', signal),

  run: (id: string, signal?: AbortSignal) =>
    getJSON<RunDetail>(`/api/runs/${encodeURIComponent(id)}`, signal),

  rollouts: (id: string, split?: string, signal?: AbortSignal) => {
    const q = split ? `?split=${encodeURIComponent(split)}` : ''
    return getJSON<RolloutRow[]>(`/api/runs/${encodeURIComponent(id)}/rollouts${q}`, signal)
  },

  rollout: (id: string, file: string, signal?: AbortSignal) =>
    getJSON<RolloutDetail>(
      `/api/runs/${encodeURIComponent(id)}/rollout/${encodeURIComponent(file)}`,
      signal,
    ),

  diff: (id: string, candidate: string, signal?: AbortSignal) =>
    getJSON<CandidateDiff>(
      `/api/runs/${encodeURIComponent(id)}/diff/${encodeURIComponent(candidate)}`,
      signal,
    ),

  memory: (id: string, signal?: AbortSignal) =>
    getJSON<MemoryResult>(`/api/runs/${encodeURIComponent(id)}/memory`, signal),

  candidateFiles: (id: string, cid: string, signal?: AbortSignal) =>
    getJSON<CandidateFile[]>(
      `/api/runs/${encodeURIComponent(id)}/candidate/${encodeURIComponent(cid)}/files`,
      signal,
    ),

  compare: (ids: string[], signal?: AbortSignal) =>
    getJSON<CompareResult>(`/api/compare?ids=${ids.map(encodeURIComponent).join(',')}`, signal),

  tree: (id: string, path = '', signal?: AbortSignal) =>
    getJSON<TreeResult>(
      `/api/runs/${encodeURIComponent(id)}/tree?path=${encodeURIComponent(path)}`,
      signal,
    ),

  file: (id: string, path: string, signal?: AbortSignal) =>
    getJSON<FileResult>(
      `/api/runs/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}`,
      signal,
    ),

  gitLog: (id: string, signal?: AbortSignal) =>
    getJSON<GitCommit[]>(`/api/runs/${encodeURIComponent(id)}/git/log`, signal),

  gitDiff: (id: string, from: string, to: string, signal?: AbortSignal) =>
    getJSON<GitDiffResult>(
      `/api/runs/${encodeURIComponent(id)}/git/diff?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
      signal,
    ),

  streamURL: (id: string) => `/api/runs/${encodeURIComponent(id)}/stream`,
}
