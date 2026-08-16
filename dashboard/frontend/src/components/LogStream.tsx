import { useMemo, useState } from 'react'
import { ChevronRight, Search } from 'lucide-react'
import type { LogRow } from '../lib/types'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

/** Kinds worth colour-coding; everything else renders neutral. Keyed on the kind
 *  prefix so an algorithm can add `gepa_whatever` without a code change here. */
function toneFor(kind: string): string {
  if (kind === 'optimizer_error' || kind === 'tamper_detected') return 'text-rejected'
  if (kind.endsWith('_warning')) return 'text-accent'
  if (kind === 'step_indecisive') return 'text-indecisive'
  if (kind === 'accept' || kind === 'finalize') return 'text-accepted'
  if (kind === 'reject') return 'text-rejected'
  if (kind === 'evaluate' || kind === 'minibatch') return 'text-primary'
  return 'text-muted-strong'
}

const PHASES = ['intake', 'baseline', 'optimize', 'finalize'] as const

function clock(t: number | null): string {
  if (t == null) return '--:--:--'
  return new Date(t * 1000).toLocaleTimeString(undefined, { hour12: false })
}

/**
 * The full activity stream: every event the run logged, with timestamp, phase, kind,
 * candidate and complete detail — filterable and searchable.
 *
 * All text arrives already control-character-stripped and length-capped by the reducer
 * (`_sanitize_text`), and is rendered as JSX text nodes, never as HTML: optimizer
 * stderr and diagnosis prose are model/subprocess-authored and must not be able to
 * inject markup.
 */
export function LogStream({ log }: { log: LogRow[] }) {
  const [q, setQ] = useState('')
  const [phase, setPhase] = useState<string>('all')
  const [kind, setKind] = useState<string>('all')
  const [open, setOpen] = useState<Set<number>>(new Set())
  const [newestFirst, setNewestFirst] = useState(true)

  const kinds = useMemo(
    () => Array.from(new Set(log.map((r) => r.kind))).sort(),
    [log],
  )

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const out = log.filter((r) => {
      if (phase !== 'all' && r.phase !== phase) return false
      if (kind !== 'all' && r.kind !== kind) return false
      if (!needle) return true
      return (
        r.kind.toLowerCase().includes(needle) ||
        (r.candidate ?? '').toLowerCase().includes(needle) ||
        r.text.toLowerCase().includes(needle) ||
        JSON.stringify(r.detail).toLowerCase().includes(needle)
      )
    })
    return newestFirst ? [...out].reverse() : out
  }, [log, q, phase, kind, newestFirst])

  if (log.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No events available for this run. Every phase writes to <code>events.jsonl</code>
          while it runs, so a run dir without one was either never started or no longer
          ships its stream — the log cannot tell you which, and the numbers above come
          from the run's own snapshot either way.
        </div>
      </Card>
    )
  }

  const toggle = (seq: number) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(seq)) next.delete(seq)
      else next.add(seq)
      return next
    })

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2.5">
        <label className="relative flex min-w-[180px] flex-1 items-center">
          <Search size={14} className="absolute left-2.5 text-muted" aria-hidden />
          <span className="sr-only">Search the activity log</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search kind, candidate, or message…"
            className="h-9 w-full rounded-md border border-border bg-surface-2 pl-8 pr-2 text-sm
                       text-foreground placeholder:text-muted"
          />
        </label>
        <Select label="phase" value={phase} onChange={setPhase} options={['all', ...PHASES]} />
        <Select label="kind" value={kind} onChange={setKind} options={['all', ...kinds]} />
        <button
          type="button"
          onClick={() => setNewestFirst((v) => !v)}
          className="h-9 cursor-pointer rounded-md border border-border bg-surface-2 px-2.5 text-xs
                     text-muted-strong hover:text-foreground"
        >
          {newestFirst ? 'newest first' : 'oldest first'}
        </button>
        <span className="tnum text-xs text-muted">
          {rows.length}/{log.length}
        </span>
      </div>

      <div className="max-h-[62vh] overflow-y-auto">
        {rows.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-muted">
            No event matches this filter.
          </p>
        )}
        <ul className="divide-y divide-border">
          {rows.map((r) => {
            const isOpen = open.has(r.seq)
            const summary = summarize(r)
            return (
              <li key={r.seq}>
                <button
                  type="button"
                  onClick={() => toggle(r.seq)}
                  aria-expanded={isOpen}
                  className="flex w-full cursor-pointer items-start gap-2 px-3 py-1.5 text-left
                             hover:bg-surface-2"
                >
                  <ChevronRight
                    size={13}
                    aria-hidden
                    className={cn(
                      'mt-1 shrink-0 text-muted transition-transform duration-150',
                      isOpen && 'rotate-90',
                    )}
                  />
                  <span className="tnum mt-px shrink-0 text-[11px] text-muted">{clock(r.t)}</span>
                  <span className="mt-px w-[68px] shrink-0 text-[10px] uppercase tracking-wide text-muted">
                    {r.phase}
                  </span>
                  <span
                    className={cn(
                      'mt-px shrink-0 font-mono text-[11px] font-semibold',
                      toneFor(r.kind),
                    )}
                  >
                    {r.kind}
                  </span>
                  {r.candidate && (
                    <span className="mt-px shrink-0 rounded bg-surface-2 px-1 font-mono text-[11px] text-muted-strong">
                      {r.candidate}
                    </span>
                  )}
                  <span className="min-w-0 flex-1 truncate text-[12px] text-muted-strong">
                    {summary}
                  </span>
                </button>
                {isOpen && (
                  <div className="space-y-2 bg-surface-2 px-3 pb-3 pl-[34px] pt-1">
                    {r.text && (
                      <pre className="scroll-x max-h-72 whitespace-pre-wrap rounded border border-border
                                      bg-background p-2 font-mono text-[11px] leading-relaxed text-muted-strong">
                        {r.text}
                      </pre>
                    )}
                    <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-[11px]">
                      {Object.entries(r.detail).map(([k, v]) => (
                        <div key={k} className="col-span-2 grid grid-cols-subgrid">
                          <dt className="font-mono text-muted">{k}</dt>
                          <dd className="tnum min-w-0 break-words text-muted-strong">
                            {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </div>
    </Card>
  )
}

/** A one-line gist of an event, built from whichever fields it happens to carry. */
function summarize(r: LogRow): string {
  const d = r.detail as Record<string, unknown>
  const bits: string[] = []
  // Split sizes, not `val` — for a `splits` event `val` is the val SIZE, which read as
  // a score ("val=12.000") next to real val scores in the same column.
  if (r.kind === 'splits') {
    return `train ${sizeOf(d.train)} · val ${sizeOf(d.val)} · test ${sizeOf(d.test)}` +
      (d.seed != null ? ` · seed ${d.seed}` : '')
  }
  if (typeof d.test_reward === 'number') bits.push(`test=${d.test_reward.toFixed(3)}`)
  if (typeof d.test_delta === 'number') bits.push(`Δ=${d.test_delta.toFixed(3)}`)
  if (d.metric) bits.push(`${d.metric} at ${d.pct}% (${d.spent} / ${d.limit})`)
  if (d.split) bits.push(`split=${d.split}`)
  if (typeof d.reward === 'number') bits.push(`reward=${d.reward.toFixed(3)}`)
  if (typeof d.val === 'number') bits.push(`val=${d.val.toFixed(3)}`)
  if (typeof d.cost_usd === 'number') bits.push(`$${d.cost_usd.toFixed(4)}`)
  if (typeof d.opt_cost_usd === 'number') bits.push(`opt $${d.opt_cost_usd.toFixed(4)}`)
  if (d.accept !== undefined) bits.push(d.accept ? 'ACCEPT' : 'reject')
  if (bits.length) return bits.join('  ')
  return r.text || Object.keys(d).join(', ')
}

/** A split field is a list of task ids or already a count. */
function sizeOf(v: unknown): string {
  if (Array.isArray(v)) return String(v.length)
  if (typeof v === 'number') return String(v)
  return '—'
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: readonly string[]
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 cursor-pointer rounded-md border border-border bg-surface-2 px-1.5 text-xs
                   text-foreground"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}
