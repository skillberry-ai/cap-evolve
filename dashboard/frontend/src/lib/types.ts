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

/** One row of reduced["summary"].per_iteration — optimizer vs runner cost/time per step.
 * Cost fields are nullable (runner cost is often $0/null on RITS); time is always set. */
export interface PerIterationCost {
  iteration: number
  candidate: string
  status: NodeStatus
  optimizer_usd: number | null
  optimizer_seconds: number
  optimizer_tokens: number
  runner_usd: number | null
  runner_seconds: number
  runner_tokens: number
}

/** One row of reduced["summary"].evaluations — a single scoring of a candidate on a
 * split. Distinct from PerIterationCost (which is optimizer-step oriented): this is
 * the eval-centric view (baseline seed-on-val, every full val eval, the sealed test).
 * cost_usd/tokens/seconds are the RUNNER spend that produced the eval. */
export interface Evaluation {
  id: string
  kind: 'baseline' | 'candidate' | 'test'
  candidate: string
  split: string
  reward: number | null
  stderr: number | null
  n_tasks: number
  trials: number
  cost_usd: number
  seconds: number
  tokens: number
}

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
  opt_cost_usd?: number | null
  opt_tokens?: number | null
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

/** One stage of the cap-evolve pipeline, as detected from events.jsonl by
 * `dashboard.derive_pipeline` (#138). `status` is monotone: done once a later phase
 * started, active for the latest started phase, pending otherwise. */
export interface PipelinePhase {
  key: string
  label: string
  status: 'done' | 'active' | 'skipped' | 'pending'
  detail: string
  started_at: number | null
  index: number
}

/** Live spend. `source: 'spent'` means these are state.json's authoritative Spent
 * totals (the same numbers the KPI strip and the budget check use); `'events'` means
 * they were accumulated from the event log by `eventstream.accrue_totals` because the
 * run has not written a Spent yet. Either way each dollar is counted exactly once. */
export interface Burn {
  usd: number
  tokens: number
  elapsed_seconds: number
  usd_per_min: number | null
  tokens_per_min: number | null
  source: 'spent' | 'events'
}

export interface Pipeline {
  phases: PipelinePhase[]
  current: string | null
  /** The newest renderable event, already sanitised by `eventstream.format_event`. */
  now: { line: string | null; t: number | null; since: number | null }
  burn: Burn
}

export interface RunSummaryDetail {
  run_id?: string
  algorithm?: string | null
  pipeline?: Pipeline
  metric_direction?: 'higher_is_better' | 'lower_is_better'
  baseline_val: number | null
  best_val: number | null
  delta_pct: number | null
  delta_abs?: number | null
  test_reward: number | null
  test_sealed?: boolean
  test_pass_k?: number | null
  counts?: { accepted: number; rejected: number; failed: number; seed: number; total: number }
  frontier?: number
  tasks?: string[]
  wall_clock_seconds?: number | null
  optimizer_seconds?: number | null
  runner_seconds?: number | null
  intake_seconds?: number | null
  cost?: {
    optimizer_usd: number | null
    runner_usd: number | null
    intake_usd?: number | null
    total_usd: number | null
  }
  tokens?: number | null
  tokens_by_role?: { runner: number; optimizer: number; intake: number }
  per_iteration?: PerIterationCost[]
  evaluations?: Evaluation[]
  intake?: { usd: number; seconds: number; tokens: number; output_summary?: string; implemented?: string[] }
  budget?: {
    max_iterations?: number
    max_metric_calls?: number
    max_usd?: number
    max_optimizer_usd?: number
    stall?: number
  } | null
  spent?: {
    iterations?: number
    metric_calls?: number
    usd?: number
    optimizer_usd?: number
    intake_usd?: number
  } | null
  budget_warnings?: { metric: string; pct: number; spent: number; limit: number }[]
  gate_warnings?: unknown[]
  diagnoses?: unknown[]
  git_log?: { hash: string; subject: string }[]
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

/** GET /api/runs/{id}/custom-view — an optional algorithm-shipped view to embed.
 *  `{}` (no url) means the run ships no custom view. */
export interface CustomView {
  title?: string
  url?: string
}

/** GET /api/runs/{id}/candidate/{cid}/files. */
export interface CandidateFile {
  name: string
  text: string
}

/** GET /api/runs/{id}/tree — a generic, format-agnostic directory listing. */
export interface TreeEntry {
  name: string
  path: string
  type: 'dir' | 'file'
  size?: number | null
  children?: TreeEntry[]
}
export interface TreeResult {
  path: string
  entries: TreeEntry[]
  truncated?: boolean
}

/** GET /api/runs/{id}/file — one text file (size-capped, binary-detected). */
export interface FileResult {
  path: string
  binary: boolean
  size: number
  truncated?: boolean
  text: string | null
}

/** GET /api/runs/{id}/git/log + /git/diff. */
export interface GitCommit {
  hash: string
  subject: string
  iter: number
}
export interface GitDiffResult {
  from: string
  to: string
  available?: boolean
  error?: string
  files: DiffFile[]
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
