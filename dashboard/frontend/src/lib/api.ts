/** Typed wrappers over the cap-evolve dashboard backend (/api/*). */
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

async function getJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} for ${url}`)
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
