/** Mirrors the Plan 1 backend payloads (see core/cap_evolve/dashboard.py schemas). */

/** Run outcome, derived by the reducer from the event log's own evidence.
 *  `interrupted` and `budget_exhausted` used to both masquerade as "live". */
export type RunStatus =
  | 'running'
  | 'awaiting_agent'
  | 'completed'
  | 'budget_exhausted'
  | 'stalled'
  | 'interrupted'
  | 'failed'
  // A run whose artifacts predate status derivation (e.g. an older static export).
  // Absence of evidence is NOT evidence of failure, so it gets its own state.
  | 'unknown'

export type Verdict = 'accept' | 'reject' | 'indecisive' | 'no measurement'

/** One row of summary.gate_decisions. Δ̄/SE/n are parsed out of the gate's own reason
 *  string; a value the gate did not record is `null` — never a stand-in 0. */
export interface GateDecision {
  iteration: number | null
  candidate: string
  verdict: Verdict
  val: number | null
  parent: string | null
  parent_val: number | null
  delta: number | null
  stderr: number | null
  n: number | null
  k_se: number | null
  threshold: number | null
  reason: string
}

/** One spend row. `usd: null` means the cost was never recorded (show "—", not $0). */
export interface CostRow {
  phase: 'intake' | 'baseline' | 'optimize' | 'finalize'
  kind: 'intake' | 'baseline_eval' | 'candidate_eval' | 'test_eval' | 'optimizer_call'
  label: string
  candidate: string | null
  split: string | null
  usd: number | null
  seconds: number
  tokens: number
  note?: string
}

export interface CostLedger {
  rows: CostRow[]
  attributed_usd: number
  total_usd: number
  /** Recorded spend the event rows cannot account for. Shown, never hidden. */
  unattributed_usd: number
  rows_missing_cost: number
  /** See RunSummary.cost.metered — $0 after real calls is missing data, not free. */
  metered?: boolean
}

/** One event from the run's append-only log, phase-tagged and sanitized. */
export interface LogRow {
  seq: number
  t: number | null
  kind: string
  phase: 'intake' | 'baseline' | 'optimize' | 'finalize'
  candidate: string | null
  detail: Record<string, unknown>
  /** Optimizer stderr / diagnosis prose, control-characters stripped. */
  text: string
}

/** Which panels this run has real data for. Absent signal ⇒ panel omitted, never faked. */
export interface RunCapabilities {
  per_task: boolean
  lineage: boolean
  gate: boolean
  cost: boolean
  log: boolean
  trajectories: boolean
  diffs: boolean
  minibatch: boolean
  gepa: boolean
  skillopt: boolean
  epochs: boolean
  focus: boolean
  evograph: boolean
  parallel: boolean
  freeform: boolean
  /** agent-optimize recorded tiered cheap screens (`screen` events + `screens/*.json`). */
  screens: boolean
}

export interface SplitsInfo {
  train: number | null
  val: number | null
  test: number | null
  seed: number | null
  /** train==val==test — the "test" number is NOT a generalization estimate. */
  no_holdout: boolean
  warning: string
}

export interface EvographRound {
  round: number | string | null
  split: string | null
  started_at: string | null
  completed_at: string | null
  num_tasks: number | null
  primary_metric: string | null
  metrics: Record<string, number | null>
  cost_usd: number | null
}

export interface EvographWeakness {
  slug: string
  status?: string
  tags?: string[]
  discovered_in_round?: string | number
  solved_in_round?: string | number
  affected_tasks?: string[]
  related?: string[]
  num_solutions?: number
  [k: string]: unknown
}

export interface AlgoExtra {
  minibatch?: { candidate: string | null; reward: number | null; n_tasks: number | null; tasks: string[]; t: number | null }[]
  gepa?: { kind: string; t: number | null; candidate: string | null; detail: Record<string, unknown> }[]
  skillopt?: { kind: string; t: number | null; epoch?: number | null; lr?: number | null; candidate: string | null; detail: Record<string, unknown> }[]
  epochs?: number[]
  focus?: string[]
  evograph?: { rounds: EvographRound[]; weaknesses: EvographWeakness[] }
  parallel?: Record<string, unknown>[]
  screens?: ScreenRow[]
}

/** One agent-optimize cheap screen: a paired subset eval that decides whether a
 *  candidate is worth a full val run. `mean_delta` is a SUBSET statistic — never a val
 *  score — and `inconclusive` means the subset could not separate the two. */
export interface ScreenRow {
  candidate: string
  screen_tag: string
  tier: number | null
  decision: string | null
  inconclusive: boolean
  mean_delta: number | null
  se: number | null
  n: number | null
  threshold: number | null
  net_rollouts: number | null
  ids: string[]
  holdout: string[]
  informative: string[]
  fixed: string[]
  regressed: string[]
  pool_n: number | null
  t: number | null
}

/** One row from GET /api/runs (light hub summary). */
export interface RunSummary {
  run_id: string
  path: string
  algorithm: string | null
  status: RunStatus
  status_reason?: string
  best_val: number | null
  baseline_val: number | null
  delta_pct: number | null
  delta_abs?: number | null
  test_reward?: number | null
  iterations: number
  total_usd: number | null
  /** False => the runner reports no cost; total_usd is missing data, not $0. */
  cost_metered?: boolean
  last_event_t?: number | null
  mtime: number
}

export type NodeStatus = 'seed' | 'accepted' | 'rejected' | 'indecisive' | 'failed'

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
  /** Tasks this candidate fixed / broke vs its parent, when the run recorded the
   *  movement. Empty (not absent-as-zero) when nothing was recorded. */
  fixed?: string[]
  broke?: string[]
  cost_usd?: number | null
  tokens?: number | null
  opt_cost_usd?: number | null
  opt_tokens?: number | null
  seconds?: number | null
  optimizer_seconds?: number | null
  runner_seconds?: number | null
  iteration?: number | null
  reason?: string | null
  /** The parent's val at the time this candidate was gated (null when not recorded). */
  parent_val?: number | null
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
  algorithm_source?: string | null
  status?: RunStatus
  status_reason?: string
  started_t?: number | null
  last_event_t?: number | null
  /** Real wall time: first event → last event when the run is over, first event → now
   *  while it is still running (see elapsed_open). Includes idle gaps, unlike
   *  wall_clock_seconds. */
  elapsed_seconds?: number | null
  /** True ⇒ elapsed_seconds has no end yet and is still growing; label it "so far". */
  elapsed_open?: boolean
  event_count?: number
  capabilities?: RunCapabilities
  splits?: SplitsInfo | null
  gate_decisions?: GateDecision[]
  cost_ledger?: CostLedger
  log?: LogRow[]
  algo_extra?: AlgoExtra
  baseline_val: number | null
  baseline_stderr?: number | null
  best_val: number | null
  best_id?: string | null
  delta_abs?: number | null
  delta_pct: number | null
  test_reward: number | null
  test_stderr?: number | null
  test_sealed?: boolean
  /** The SEED's score on the same sealed test split, and best − seed on test. A sealed
   *  test number means nothing without it: `test_delta === 0` is the normal reading for
   *  a run whose best candidate is the seed. */
  test_baseline_reward?: number | null
  test_delta?: number | null
  /** {k: pass^k}. A k is ABSENT when k > num_trials (undefined ⇒ show "N/A", never 0). */
  test_pass_k?: Record<string, number> | null
  counts?: {
    accepted: number
    rejected: number
    /** ABSENT in older/static exports — never interpolate it unguarded. */
    indecisive?: number
    failed: number
    seed: number
    total: number
  }
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
    /** False when the run made real calls yet reports exactly $0 — the runner does
     *  not report cost (self-hosted vLLM, an internal endpoint, a proxy that returns
     *  no usage). Render "not metered", never "$0.000": nobody measured that. */
    metered?: boolean
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
  baseline_stderr?: number | null
  best_val: number | null
  delta_pct: number | null
  test_reward: number | null
  total_usd: number | null
  cost_metered?: boolean
  tokens: number | null
  iterations: number
  status?: RunStatus
  splits?: SplitsInfo | null
  /** The val task ids this run's means are over. Runs with different task sets are NOT
   *  comparable — the view says so rather than putting them in one chart silently. */
  tasks?: string[]
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
