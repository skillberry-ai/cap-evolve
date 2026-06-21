import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { RunGraph } from '../lib/types'
import { pct } from '../lib/format'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { DiffFileView } from './DiffRows'

/** Per-candidate diff vs parent — what changed each iteration, and did it help. */
export function IterationsDiff({ runId, graph }: { runId: string; graph: RunGraph }) {
  // Candidates with a parent (i.e. an actual change), newest first.
  const candidates = useMemo(
    () =>
      [...graph.nodes]
        .filter((n) => n.parent)
        .sort((a, b) => (b.iteration ?? 0) - (a.iteration ?? 0)),
    [graph.nodes],
  )
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes])
  const [cid, setCid] = useState<string | undefined>(candidates[0]?.id)

  const { data, isLoading } = useQuery({
    queryKey: ['diff', runId, cid],
    queryFn: ({ signal }) => api.diff(runId, cid!, signal),
    enabled: !!cid,
  })

  if (candidates.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No iteration diffs — candidate snapshots weren’t recorded for this run.
        </div>
      </Card>
    )
  }

  const node = cid ? byId.get(cid) : undefined
  const parent = node?.parent ? byId.get(node.parent) : undefined
  const delta =
    node?.val != null && parent?.val != null ? node.val - parent.val : null

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label htmlFor="cand" className="text-sm text-muted">
          candidate
        </label>
        <select
          id="cand"
          value={cid}
          onChange={(e) => setCid(e.target.value)}
          className="rounded border border-border bg-surface-2 px-2 py-1 text-sm"
        >
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id} · {c.status} · {pct(c.val)}
            </option>
          ))}
        </select>
        {parent && (
          <span className="tnum text-xs text-muted">
            vs {parent.id}
            {delta != null && (
              <>
                {' '}· Δ{' '}
                <span className={delta >= 0 ? 'text-accepted' : 'text-rejected'}>{pct(delta)}</span>
              </>
            )}
          </span>
        )}
      </div>

      {isLoading && <Skeleton className="h-48 w-full" />}
      {data && data.files.length === 0 && (
        <p className="py-8 text-center text-sm text-muted">No file changes recorded for this candidate.</p>
      )}

      {data?.files.map((f) => (
        <DiffFileView key={f.path} file={f} />
      ))}
    </Card>
  )
}
