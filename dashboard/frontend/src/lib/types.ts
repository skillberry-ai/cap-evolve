/** Mirrors the Plan 1 backend payloads (see core/cap_evolve/dashboard.py schemas). */

export type RunStatus = 'live' | 'done' | 'failed'

/** One row from GET /api/runs (light hub summary). */
export interface RunSummary {
  run_id: string
  path: string
  algorithm: string | null
  status: RunStatus
  best_val: number | null
  baseline_val: number | null
  delta_pct: number | null
  iterations: number
  total_usd: number | null
  mtime: number
}

export type NodeStatus = 'seed' | 'accepted' | 'rejected' | 'failed'

/** A candidate in reduced["graph"].nodes. */
export interface GraphNode {
  id: string
  parent: string | null
  children: string[]
  status: NodeStatus
  val: number | null
  stderr?: number | null
  per_task?: Record<string, number>
  feedback?: Record<string, string>
  cost_usd?: number | null
  tokens?: number | null
  seconds?: number | null
  optimizer_seconds?: number | null
  runner_seconds?: number | null
  iteration?: number | null
  reason?: string | null
  epoch?: number
  merge_of?: string[]
  best_so_far?: boolean
}

export interface RunGraph {
  nodes: GraphNode[]
  root: string
  best_id: string | null
}

export interface RunSummaryDetail {
  run_id?: string
  algorithm?: string | null
  baseline_val: number | null
  best_val: number | null
  delta_pct: number | null
  test_reward: number | null
  test_sealed?: boolean
  test_pass_k?: number | null
  counts?: { accepted: number; rejected: number; failed: number; seed: number; total: number }
  frontier?: number
  tasks?: string[]
  wall_clock_seconds?: number | null
  optimizer_seconds?: number | null
  runner_seconds?: number | null
  cost?: { optimizer_usd: number | null; runner_usd: number | null; total_usd: number | null }
  tokens?: number | null
  gate_warnings?: unknown[]
  diagnoses?: unknown[]
  git_log?: unknown[]
}

/** GET /api/runs/{id}. */
export interface RunDetail {
  run_id: string
  path: string
  graph: RunGraph
  summary: RunSummaryDetail
}

/** GET /api/runs/{id}/rollouts. */
export interface RolloutRow {
  task_id: string
  candidate: string
  trial: number
  split: string
  reward: number | null
  feedback: string
  file: string
}

/** One file in GET /api/runs/{id}/diff/{candidate}. */
export interface DiffFile {
  path: string
  added: number
  removed: number
  rows: { t: 'add' | 'del' | 'ctx' | 'hunk'; l: string }[]
}

export interface CandidateDiff {
  candidate: string
  parent: string | null
  files: DiffFile[]
}

/** GET /api/compare. */
export interface CompareRow {
  run_id: string
  algorithm: string | null
  baseline_val: number | null
  best_val: number | null
  delta_pct: number | null
  test_reward: number | null
  total_usd: number | null
  tokens: number | null
  iterations: number
  series: { iteration: number; best_so_far: number }[]
}

export interface CompareResult {
  runs: CompareRow[]
  tasks: string[]
}

/** GET /api/runs/{id}/memory. */
export interface HistoryEntry {
  candidate_id: string
  summary: string
  val: number | null
}
export interface RejectedEntry {
  candidate_id: string
  summary: string
  reason: string
  val: number | null
}
export interface MemoryResult {
  history: HistoryEntry[]
  rejected: RejectedEntry[]
}

/** GET /api/runs/{id}/candidate/{cid}/files. */
export interface CandidateFile {
  name: string
  text: string
}

/** GET /api/runs/{id}/rollout/{file}. */
export interface RolloutDetail {
  input?: unknown
  rollout?: {
    output?: unknown
    trace?: string
    tool_calls?: Array<{ name?: string; [k: string]: unknown }>
    error?: string | null
    [k: string]: unknown
  }
  score?: { reward?: number | null; feedback?: string; [k: string]: unknown }
}

/** SSE frames from GET /api/runs/{id}/stream. */
export type StreamEvent =
  | { type: 'snapshot'; data: RunDetail }
  | { type: 'event'; data: Record<string, unknown> }
  | { type: 'done'; data: { run_id: string } }
  | { type: 'idle'; data: { run_id: string } }
