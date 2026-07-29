/** Play-by-play of the run's event stream (newest first).
 *
 * The stream buffer already exists (useRunStream keeps a capped 200-entry log);
 * this only renders it. Read-only, no fetching of its own. The SSE route replays
 * the run's whole log from offset 0 before tailing, so a FINISHED run shows its
 * history rather than an empty panel.
 */
import { CheckCircle2, XCircle } from 'lucide-react'
import { Card } from './ui/Card'
import { pct } from '../lib/format'
import { cn } from '../lib/cn'
import { LOG_CAP, type StreamEntry, type StreamStatus } from '../lib/useRunStream'

/** An event's accept/reject verdict, when it carries one. */
function verdict(d: Record<string, unknown>): 'accepted' | 'rejected' | null {
  return typeof d.accept === 'boolean' ? (d.accept ? 'accepted' : 'rejected') : null
}

/** The one-line human summary of an event: candidate, val, and why. */
function detail(d: Record<string, unknown>): string {
  const bits: string[] = []
  // Algorithms name the candidate field differently (candidate | candidate_id),
  // same normalisation the reducer does in dashboard.py:_step_candidate.
  const cid = d.candidate ?? d.candidate_id
  if (cid) bits.push(String(cid))
  const val = d.val ?? d.reward
  if (typeof val === 'number') bits.push(`val ${pct(val)}`)
  // `name` is the `algorithm` event's only field — without it that row renders blank.
  const why = d.reason ?? d.error ?? d.stop_reason ?? d.note ?? d.name
  if (typeof why === 'string' && why) bits.push(why)
  return bits.join(' · ')
}

/** Truthful empty state: say *why* it's empty, never imply the run was silent. */
function emptyMessage(status: StreamStatus): string {
  if (status === 'connecting') return 'Connecting to the event stream…'
  if (status === 'error') return 'Event stream unavailable — reload to reconnect.'
  if (status === 'done' || status === 'idle')
    return 'This run logged no events. See Iterations / Phases for its history.'
  return 'No events yet — this run has just started.'
}

export function EventTicker({
  log,
  status = 'live',
}: {
  log: StreamEntry[]
  status?: StreamStatus
}) {
  if (!log.length) {
    return (
      <Card>
        <div className="p-4 text-sm text-muted">{emptyMessage(status)}</div>
      </Card>
    )
  }
  return (
    <Card>
      {/* aria-live so a screen reader hears new events without polling the DOM. */}
      <ul
        aria-live="polite"
        aria-label="Live event feed"
        className="max-h-72 divide-y divide-border overflow-y-auto text-xs"
      >
        {[...log].reverse().map((e) => {
          const v = verdict(e.data)
          return (
            <li key={e.seq} className="flex items-baseline gap-2 px-3 py-1.5">
              <span className="tnum w-10 shrink-0 text-right text-muted">{e.seq + 1}</span>
              <span
                className={cn(
                  'inline-flex shrink-0 items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono',
                  v === 'accepted' && 'text-accepted',
                  v === 'rejected' && 'text-rejected',
                )}
              >
                {/* Icon, not colour alone (WCAG 1.4.1) — same pairing as StatusBadge. */}
                {v === 'accepted' && <CheckCircle2 size={11} aria-label="accepted" />}
                {v === 'rejected' && <XCircle size={11} aria-label="rejected" />}
                {e.kind}
              </span>
              <span className="truncate text-muted">{detail(e.data)}</span>
            </li>
          )
        })}
        {log.length >= LOG_CAP && (
          <li className="px-3 py-1.5 text-muted">showing the last {LOG_CAP} events</li>
        )}
      </ul>
    </Card>
  )
}
