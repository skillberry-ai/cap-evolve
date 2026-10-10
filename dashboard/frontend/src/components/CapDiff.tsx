import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { CapDiffFile, CapDiffResult, CapDiffRow, RunGraph } from '../lib/types'
import { cn } from '../lib/cn'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'

const FIXED_BASES = ['parent', 'latest_base', 'original', 'selected', 'ancestry'] as const

/** Merge-hunk class -> style. Each class differs in border STYLE and a text chip, not only
 *  hue, so they stay distinct for colour-blind reviewers. */
export function classStyle(c: string): { key: string; label: string; border: string; color: string } {
  if (c === 'new') return { key: 'new', label: 'merge-specific', border: 'border-solid', color: 'var(--series-5)' }
  if (c === 'reverted') return { key: 'reverted', label: 'reverted', border: 'border-dotted', color: 'var(--series-4)' }
  return { key: 'inherited', label: c.replace('inherited:', 'inherited from '), border: 'border-dashed', color: 'var(--series-1)' }
}

const ROW = {
  add: 'bg-accepted/10 text-accepted',
  del: 'bg-rejected/10 text-rejected',
  hunk: 'text-primary',
  ctx: 'text-muted',
} as const

function Rows({ rows }: { rows: CapDiffRow[] }) {
  return (
    <pre className="rounded-b bg-background text-xs leading-relaxed">
      {rows.map((r, i) => {
        const st = r.c ? classStyle(r.c) : null
        const chip = r.c && r.c !== rows[i - 1]?.c
        return (
          <div
            key={i}
            data-class={st?.key}
            className={cn('whitespace-pre-wrap break-words pl-6 -indent-4 pr-2', ROW[r.t], st && cn('border-l-4', st.border))}
            style={st ? { borderLeftColor: st.color } : undefined}
          >
            {chip && st && (
              <span className="mr-2 rounded border px-1 text-[10px] uppercase tracking-wide" style={{ borderColor: st.color, color: st.color }}>
                {st.label}
              </span>
            )}
            {r.l || ' '}
          </div>
        )
      })}
    </pre>
  )
}

function Files({ files }: { files: CapDiffFile[] }) {
  if (files.length === 0) return <p className="py-6 text-center text-sm text-muted">No capability changes.</p>
  return (
    <>
      {files.map((f) => (
        <div key={f.path} className="mb-3 rounded border border-border">
          <div className="flex items-center gap-2 border-b border-border px-2 py-1">
            <span className="truncate font-mono text-xs">{f.path}</span>
            <span className="tnum ml-auto text-xs text-accepted">+{f.added}</span>
            <span className="tnum text-xs text-rejected">−{f.removed}</span>
          </div>
          <Rows rows={f.rows} />
        </div>
      ))}
    </>
  )
}

function Legend() {
  return (
    <div className="mb-3 flex flex-wrap gap-3 text-[11px] text-muted" data-testid="capdiff-legend">
      {['inherited:A', 'reverted', 'new'].map((c) => {
        const st = classStyle(c)
        return (
          <span key={c} className="inline-flex items-center gap-1.5">
            <span className={cn('inline-block h-3 w-3 border-l-4', st.border)} style={{ borderLeftColor: st.color }} />
            {c === 'inherited:A' ? 'inherited (from a parent)' : st.label}
          </span>
        )
      })}
    </div>
  )
}

function Result({ r }: { r: CapDiffResult }) {
  if (r.mode === 'ancestry') {
    return (
      <div>
        {(r.edges ?? []).map((e) => (
          <section key={`${e.from}-${e.to}`} className="mb-4" aria-label={`edge ${e.from} to ${e.to}`}>
            <h4 className="mb-1 text-xs font-medium">
              {e.from} → {e.to} {e.merge && <span className="text-muted">(merge of {e.parents.join(' + ')}, base {e.base})</span>}
            </h4>
            <Files files={e.files} />
          </section>
        ))}
        {r.blame && Object.keys(r.blame).length > 0 && (
          <section aria-label="blame">
            <h4 className="mb-1 text-xs font-medium">Who introduced each line (final version)</h4>
            {Object.entries(r.blame).map(([path, runs]) => (
              <div key={path} className="mb-1 text-xs">
                <span className="font-mono">{path}</span>{' '}
                <span className="text-muted">
                  {runs.map((b) => `${b.start === b.end ? b.start : `${b.start}-${b.end}`}: ${b.by}`).join(' · ')}
                </span>
              </div>
            ))}
          </section>
        )}
      </div>
    )
  }
  return (
    <div>
      <p className="mb-2 text-xs text-muted">
        {r.target} vs <span className="font-mono">{r.base}</span>
        {r.merge && ` — merge of ${r.parents?.join(' + ')}`}
      </p>
      <Files files={r.files ?? []} />
    </div>
  )
}

/** Capability-only diff with a base selector. Merge parents of a multi-parent node are
 *  offered as extra bases; a merge result's own hunks are classified by the backend. */
export function CapDiff({ runId, graph }: { runId: string; graph: RunGraph }) {
  const candidates = useMemo(
    () => [...graph.nodes].filter((n) => n.parent || n.parents?.length).sort((a, b) => (b.iteration ?? 0) - (a.iteration ?? 0)),
    [graph.nodes],
  )
  const [target, setTarget] = useState<string | undefined>(candidates[0]?.id)
  const [base, setBase] = useState<string>('parent')
  const node = graph.nodes.find((n) => n.id === target)
  const mergeParents = node?.parents && node.parents.length > 1 ? node.parents : []

  const { data, isLoading, error } = useQuery({
    queryKey: ['capdiff', runId, target, base],
    queryFn: ({ signal }) => api.capdiff(runId, target!, base, signal),
    enabled: !!target,
    retry: false,
  })

  if (candidates.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No capability diffs — candidate snapshots weren’t recorded for this run.
        </div>
      </Card>
    )
  }
  const sel = 'rounded border border-border bg-surface-2 px-2 py-1 text-sm'
  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label htmlFor="capdiff-target" className="text-sm text-muted">candidate</label>
        <select id="capdiff-target" value={target} onChange={(e) => { setTarget(e.target.value); setBase('parent') }} className={sel}>
          {candidates.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.status}</option>)}
        </select>
        <label htmlFor="capdiff-base" className="text-sm text-muted">compare against</label>
        <select id="capdiff-base" value={base} onChange={(e) => setBase(e.target.value)} className={sel}>
          {FIXED_BASES.map((b) => <option key={b} value={b}>{b.replace('_', ' ')}</option>)}
          {mergeParents.map((p) => <option key={p} value={p}>merge parent {p}</option>)}
        </select>
      </div>
      <Legend />
      {isLoading && <Skeleton className="h-48 w-full" />}
      {error && <p className="py-6 text-center text-sm text-rejected">{(error as Error).message}</p>}
      {data && <Result r={data} />}
    </Card>
  )
}
