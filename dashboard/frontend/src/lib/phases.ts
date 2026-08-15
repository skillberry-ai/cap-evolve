/** Derive the pipeline phase timeline from a reduced run (no extra backend data). */
import type { RunDetail } from './types'

export type PhaseStatus = 'done' | 'active' | 'pending'

export interface PhaseStep {
  key: string
  label: string
  status: PhaseStatus
  detail: string
  metrics: { label: string; value: string }[]
}

const pctStr = (v: number | null | undefined) =>
  v == null || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(1)}%`

/**
 * The cap-evolve sequence is intake → implement-and-check → baseline →
 * algorithm → finalize → report. We infer each phase's status from the reduced
 * summary/graph: a run that produced candidates has cleared intake/check/baseline;
 * a sealed test means finalize ran; the dashboard existing means report ran.
 */
export function derivePhases(detail: RunDetail): PhaseStep[] {
  const s = detail.summary
  const counts = s.counts
  const evaluated = (counts?.accepted ?? 0) + (counts?.rejected ?? 0)
  const hasBaseline = s.baseline_val != null
  const finalized = s.test_reward != null || !!s.test_sealed
  const algorithmActive = !finalized && evaluated > 0

  const done = (b: boolean): PhaseStatus => (b ? 'done' : 'pending')

  // Intake is only "done" when the run dir actually RECORDS an intake: an intake event
  // (which carries its own summary) or intake spend. Inferring it from "some candidate
  // exists" claimed a phase ran on the strength of a later phase's output — a fabricated
  // status, and the reducer now gives us the evidence to avoid it.
  const intake = s.intake
  const intakeRecorded = Boolean(
    intake && (intake.usd || intake.seconds || intake.tokens || intake.output_summary),
  )

  return [
    {
      key: 'intake',
      label: 'Intake',
      status: intakeRecorded ? 'done' : 'pending',
      detail: intakeRecorded
        ? intake?.output_summary || 'Interviewed + scaffolded the project, adapter, and seed.'
        : 'No intake was recorded in this run dir — the project was scaffolded elsewhere.',
      metrics: intakeRecorded
        ? [{ label: 'intake cost', value: `$${(intake?.usd ?? 0).toFixed(4)}` }]
        : [],
    },
    {
      key: 'check',
      label: 'Implement & check',
      // The hard gate leaves no event of its own; a scored baseline is proof it passed
      // (nothing gets evaluated until it does), and that is the only claim made here.
      status: done(hasBaseline),
      detail: hasBaseline
        ? 'Passed: nothing is evaluated until cap-evolve check succeeds.'
        : 'Not yet evidenced — no baseline has been scored.',
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
