import { AlertTriangle, Cpu, Lock, Unlock } from 'lucide-react'
import type { RunSummaryDetail } from '../lib/types'
import { StatusBadge } from './StatusBadge'
import { duration } from '../lib/format'
import { Card } from './ui/Card'

function ago(t: number | null | undefined): string | null {
  if (!t) return null
  const s = Date.now() / 1000 - t
  if (s < 90) return 'just now'
  return `${duration(s)} ago`
}

/**
 * Run identity + the two things a reader must not get wrong: what state the run is
 * actually in, and whether its test number means anything.
 */
export function RunHeader({
  runId,
  summary,
  liveEvents,
}: {
  runId: string
  summary: RunSummaryDetail
  liveEvents?: number
}) {
  const splits = summary.splits
  const sealed = summary.test_sealed
  const noHoldout = splits?.no_holdout

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{runId}</h1>
        <StatusBadge status={summary.status} reason={summary.status_reason} />

        {summary.algorithm ? (
          <span
            title={`Algorithm identified from ${summary.algorithm_source ?? 'unknown evidence'}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-primary/40
                       bg-primary-soft px-2.5 py-1 text-xs font-medium text-primary"
          >
            <Cpu size={12} aria-hidden />
            {summary.algorithm}
          </span>
        ) : (
          <span
            title="No algorithm-specific event and no project spec — the reducer will not guess."
            className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted"
          >
            algorithm not recorded
          </span>
        )}

        <span
          title={
            sealed
              ? 'The test split was reserved and scored exactly once.'
              : 'The test split has not been scored — there is no headline number yet.'
          }
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2
                     px-2.5 py-1 text-xs text-muted"
        >
          {sealed ? <Lock size={12} aria-hidden /> : <Unlock size={12} aria-hidden />}
          {sealed ? 'test sealed' : 'test not sealed'}
        </span>

        <div className="tnum ml-auto flex items-center gap-3 text-xs text-muted">
          {summary.elapsed_seconds != null && (
            <span title="First to last event — includes idle gaps, unlike measured wall clock.">
              {duration(summary.elapsed_seconds)} elapsed
            </span>
          )}
          {ago(summary.last_event_t) && <span>last event {ago(summary.last_event_t)}</span>}
          {liveEvents ? <span className="text-primary">{liveEvents} live</span> : null}
        </div>
      </div>

      {summary.status_reason && summary.status !== 'completed' && (
        <p className="text-[12px] leading-relaxed text-muted">{summary.status_reason}</p>
      )}

      {(noHoldout || splits?.warning) && (
        <Card className="border-accent/50 bg-accent/[0.05]">
          <div className="flex gap-2.5 p-3">
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-accent" aria-hidden />
            <div className="text-[12px] leading-relaxed text-muted-strong">
              {noHoldout && (
                <p>
                  <span className="font-medium text-accent">No holdout.</span> This run's
                  train, val and test splits contain the same tasks, so the "test" number
                  is <em>not</em> a generalization estimate — the optimizer saw those
                  tasks. Read it as a sanity check only.
                </p>
              )}
              {splits?.warning && <p className={noHoldout ? 'mt-1' : ''}>{splits.warning}</p>}
            </div>
          </div>
        </Card>
      )}

      {splits && (
        <p className="tnum text-[11px] text-muted">
          splits · train {splits.train ?? '—'} · val {splits.val ?? '—'} · test{' '}
          {splits.test ?? '—'}
          {splits.seed != null && ` · seed ${splits.seed}`}
          <span className="ml-3 border-l border-border pl-3">
            val decides selection; test is scored exactly once and never optimized against.
          </span>
        </p>
      )}
    </div>
  )
}
