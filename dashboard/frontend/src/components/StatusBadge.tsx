import type { NodeStatus, RunStatus, Verdict } from '../lib/types'
import { NODE_STATUS, RUN_STATUS, VERDICT } from '../lib/verdict'
import { cn } from '../lib/cn'

/** Run status pill. Colour is never the sole signal — icon + label always present,
 *  and `reason` (the reducer's evidence) is the accessible title. */
export function StatusBadge({
  status,
  reason,
  className,
}: {
  status: RunStatus | undefined
  reason?: string
  className?: string
}) {
  // Falls back to `unknown`, never `failed`: an absent status means the run dir carries no
  // evidence either way (an older export, say), and rendering that as a red "failed" pill
  // asserts a verdict nothing in the data supports.
  const meta = (status && RUN_STATUS[status]) || RUN_STATUS.unknown
  const { label, tone, ring, Icon, blurb } = meta
  return (
    <span
      title={reason ? `${blurb}\n${reason}` : blurb}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border bg-surface-2 px-2.5 py-1',
        'text-xs font-medium',
        tone,
        ring,
        className,
      )}
    >
      <span className="relative inline-flex">
        {status === 'running' && (
          <span
            aria-hidden
            className="absolute inset-0 rounded-full animate-pulse-ring"
            style={{ background: 'var(--primary)' }}
          />
        )}
        <Icon size={13} className="relative" aria-hidden />
      </span>
      {label}
    </span>
  )
}

/** Candidate verdict / node status chip — the accept · reject · indecisive · failed
 *  distinction the honesty contract requires the UI to keep visible. */
export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: Verdict | NodeStatus
  className?: string
}) {
  const meta =
    (VERDICT as Record<string, typeof VERDICT.accept>)[verdict] ??
    (NODE_STATUS as Record<string, typeof VERDICT.accept>)[verdict] ??
    NODE_STATUS.failed
  const { label, tone, ring, Icon, blurb } = meta
  return (
    <span
      title={blurb}
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium',
        tone,
        ring,
        className,
      )}
    >
      <Icon size={11} aria-hidden />
      {label}
    </span>
  )
}
