import { AlertTriangle, CheckCircle2, CircleDot, PlugZap, XCircle } from 'lucide-react'
import type { RunStatus } from '../lib/types'
import { cn } from '../lib/cn'

const MAP: Record<RunStatus, { label: string; tone: string; Icon: typeof CircleDot; live?: boolean }> = {
  live: { label: 'live', tone: 'text-accent', Icon: CircleDot, live: true },
  done: { label: 'done', tone: 'text-accepted', Icon: CheckCircle2 },
  failed: { label: 'failed', tone: 'text-rejected', Icon: XCircle },
  // #118: a run that went quiet or died must not read as a clean finish.
  stalled: { label: 'stalled', tone: 'text-warn', Icon: AlertTriangle },
  crashed: { label: 'crashed', tone: 'text-rejected', Icon: PlugZap },
}

/** Status pill. Color is never the sole signal — icon + label always present. */
export function StatusBadge({
  status,
  detail,
  className,
}: {
  status: RunStatus
  /** Why, with the numbers — the reason a user can act on ("no events for 42m, over
   * this run's own threshold 12m"). Rendered as the accessible title (#118). */
  detail?: string | null
  className?: string
}) {
  const { label, tone, Icon, live } = MAP[status] ?? MAP.failed
  return (
    <span
      title={detail ?? undefined}
      className={cn('inline-flex items-center gap-1.5 text-xs font-medium', tone, className)}
    >
      <span className="relative inline-flex">
        {live && (
          <span
            aria-hidden
            className="absolute inset-0 rounded-full animate-pulse-ring"
            style={{ background: 'var(--accent)' }}
          />
        )}
        <Icon size={14} className="relative" aria-hidden />
      </span>
      {label}
    </span>
  )
}
