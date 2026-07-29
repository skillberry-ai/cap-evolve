/** Live play-by-play of the SSE event stream (newest first).
 *
 * The stream buffer already exists (useRunStream keeps a capped 200-entry log);
 * this only renders it. Read-only, no fetching of its own.
 */
import { Card } from './ui/Card'
import { pct } from '../lib/format'
import { cn } from '../lib/cn'
import type { StreamEntry } from '../lib/useRunStream'

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
  const why = d.reason ?? d.error ?? d.stop_reason ?? d.note
  if (typeof why === 'string' && why) bits.push(why)
  return bits.join(' · ')
}

export function EventTicker({ log }: { log: StreamEntry[] }) {
  if (!log.length) {
    return (
      <Card>
        <div className="p-4 text-sm text-muted">No live events yet.</div>
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
                  'shrink-0 rounded bg-surface-2 px-1.5 py-0.5 font-mono',
                  v === 'accepted' && 'text-accepted',
                  v === 'rejected' && 'text-rejected',
                )}
              >
                {e.kind}
              </span>
              <span className="truncate text-muted">{detail(e.data)}</span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
