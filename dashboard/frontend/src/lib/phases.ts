/** Derive the pipeline phase timeline from a reduced run (no extra backend data). */
import type { PipelinePhaseStatus, RunDetail } from './types'

/** Alias of the backend's status union, so a new status can't be added on one side
 * only — `PhasesTimeline` and `PhasePipeline` then fail to compile until handled. */
export type PhaseStatus = PipelinePhaseStatus

export interface PhaseStep {
  key: string
  label: string
  status: PhaseStatus
  detail: string
  metrics: { label: string; value: string }[]
}

/** How each status reads. One table, consumed by every phase renderer, so the compact
 * pipeline and the timeline cards can never label the same status differently.
 * `word` is what a screen reader gets; `glyph` is decorative (always `aria-hidden`).
 * Exhaustive over `PhaseStatus` by type, so adding a status fails to compile here. */
export const PHASE_PRESENTATION: Record<
  PhaseStatus,
  { glyph: string; word: string; tone: 'good' | 'live' | 'bad' | 'muted' }
> = {
  done: { glyph: '✓', word: 'done', tone: 'good' },
  active: { glyph: '●', word: 'active', tone: 'live' },
  // Where the run STOPPED, not what is running: liveness says the process is gone or
  // wedged, so this must not read as active (#234).
  interrupted: { glyph: '⏸', word: 'interrupted — the run is no longer progressing', tone: 'bad' },
  errored: { glyph: '✕', word: 'errored — reached, but it produced nothing', tone: 'bad' },
  skipped: { glyph: '–', word: 'skipped', tone: 'muted' },
  // Not a tick and not a skip: the evidence simply is not there.
  unknown: { glyph: '?', word: 'unknown — no event attests this phase', tone: 'muted' },
  pending: { glyph: '○', word: 'pending', tone: 'muted' },
}

const pctStr = (v: number | null | undefined) =>
  v == null || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(1)}%`

/** Per-phase metrics, keyed by the backend's phase key (and the legacy key below). */
function metricsFor(key: string, s: RunDetail['summary']): PhaseStep['metrics'] {
  const c = s.counts
  if (key === 'baseline') return [{ label: 'seed val', value: pctStr(s.baseline_val) }]
  if (key === 'optimize' || key === 'algorithm')
    return [
      { label: 'iterations', value: String((c?.accepted ?? 0) + (c?.rejected ?? 0)) },
      { label: 'accepted', value: String(c?.accepted ?? 0) },
      { label: 'best val', value: pctStr(s.best_val) },
    ]
  if (key === 'finalize') return [{ label: 'sealed test', value: pctStr(s.test_reward) }]
  return []
}

/**
 * The cap-evolve sequence is intake → implement-and-check → baseline →
 * algorithm → finalize → report.
 *
 * The backend detects phases from the event log itself (`summary.pipeline`, #138) —
 * enumerating every kind each of the three deterministic algorithms emits, so GEPA's
 * `gepa_val_gate` and SkillOpt's `skillopt_step` light the Optimize stage exactly like
 * hill-climb's `step`. When it's present we use it verbatim and only attach the display
 * metrics. The summary-shaped inference below stays as the fallback for a reduced
 * payload written before #138 (a cached dashboard.html, a checked-in fixture).
 */
export function derivePhases(detail: RunDetail): PhaseStep[] {
  const fromBackend = detail.summary.pipeline?.phases
  if (fromBackend?.length) {
    return fromBackend.map((p) => ({
      key: p.key,
      label:
        p.key === 'optimize' && detail.summary.algorithm
          ? `${p.label} · ${detail.summary.algorithm}`
          : p.label,
      status: p.status,
      detail: p.detail,
      metrics: metricsFor(p.key, detail.summary),
    }))
  }
  const s = detail.summary
  const counts = s.counts
  const total = counts?.total ?? detail.graph.nodes.length
  const evaluated = (counts?.accepted ?? 0) + (counts?.rejected ?? 0)
  const hasBaseline = s.baseline_val != null
  const finalized = s.test_reward != null || !!s.test_sealed
  const algorithmActive = !finalized && evaluated > 0

  const done = (b: boolean): PhaseStatus => (b ? 'done' : 'pending')

  return [
    {
      key: 'intake',
      label: 'Intake',
      status: done(total > 0 || hasBaseline),
      detail: 'Interview + scaffold the project, adapter, and seed capability.',
      metrics: [],
    },
    {
      key: 'check',
      // A pre-#138 payload carries no event log, so nothing here can attest the hard
      // gate — `total > 0 || hasBaseline` only proves the run got PAST it, which is not
      // the same as proving it passed (#234 finding 1). `unknown`, not a green tick.
      label: 'Implement & check',
      status: 'unknown',
      detail: 'Hard gate: the adapter must pass cap-evolve check before any budget is spent.',
      metrics: [],
    },
    {
      key: 'baseline',
      label: 'Baseline',
      status: done(hasBaseline),
      detail: 'Freeze train/val/test splits; score the seed on validation.',
      metrics: [{ label: 'seed val', value: pctStr(s.baseline_val) }],
    },
    {
      key: 'algorithm',
      label: `Optimize${s.algorithm ? ` · ${s.algorithm}` : ''}`,
      status: finalized ? 'done' : algorithmActive ? 'active' : hasBaseline ? 'active' : 'pending',
      detail: 'Propose → evaluate → gate by significance → snapshot. Repeat.',
      metrics: [
        { label: 'iterations', value: String(evaluated) },
        { label: 'accepted', value: String(counts?.accepted ?? 0) },
        { label: 'best val', value: pctStr(s.best_val) },
      ],
    },
    {
      key: 'finalize',
      label: 'Finalize',
      status: finalized ? 'done' : 'pending',
      detail: 'Score the best candidate once on the sealed test split.',
      metrics: [{ label: 'sealed test', value: pctStr(s.test_reward) }],
    },
    {
      key: 'report',
      label: 'Report',
      status: finalized ? 'done' : 'pending',
      detail: 'This dashboard — baseline → best → sealed test, fully explained.',
      metrics: [],
    },
  ]
}
