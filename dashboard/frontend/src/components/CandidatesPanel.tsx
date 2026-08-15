import { useMemo, useState } from 'react'
import { Star } from 'lucide-react'
import type { RunGraph, RunSummaryDetail } from '../lib/types'
import { LineageTree } from './LineageTree'
import { VerdictBadge } from './StatusBadge'
import { Card } from './ui/Card'
import { duration, pct, usd } from '../lib/format'
import { cn } from '../lib/cn'

type SortKey = 'iteration' | 'val' | 'delta'

/**
 * Every candidate: the lineage DAG plus a sortable table. Works for all algorithms —
 * a candidate is a candidate whether a deterministic loop or an agent produced it, and
 * merge parents (gepa) are drawn as extra edges rather than a separate view.
 */
export function CandidatesPanel({
  graph,
  summary,
}: {
  graph: RunGraph
  summary: RunSummaryDetail
}) {
  const [sort, setSort] = useState<SortKey>('iteration')

  const rows = useMemo(() => {
    const withDelta = graph.nodes.map((n) => ({
      ...n,
      delta: n.val != null && n.parent_val != null ? n.val - n.parent_val : null,
    }))
    const cmp = {
      iteration: (a: typeof withDelta[number], b: typeof withDelta[number]) =>
        (a.iteration ?? 0) - (b.iteration ?? 0),
      val: (a: typeof withDelta[number], b: typeof withDelta[number]) =>
        (b.val ?? -Infinity) - (a.val ?? -Infinity),
      delta: (a: typeof withDelta[number], b: typeof withDelta[number]) =>
        (b.delta ?? -Infinity) - (a.delta ?? -Infinity),
    }[sort]
    return [...withDelta].sort(cmp)
  }, [graph.nodes, sort])

  return (
    <div className="space-y-5">
      <LineageTree graph={graph} />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3.5 py-2.5">
          <h3 className="text-[13px] font-semibold">
            {rows.length} candidate{rows.length === 1 ? '' : 's'}
          </h3>
          <div className="flex items-center gap-1 text-[11px]">
            <span className="text-muted">sort</span>
            {(['iteration', 'val', 'delta'] as SortKey[]).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setSort(k)}
                aria-pressed={sort === k}
                className={cn(
                  'cursor-pointer rounded border px-1.5 py-0.5',
                  sort === k
                    ? 'border-primary/60 bg-primary-soft text-primary'
                    : 'border-border text-muted hover:text-foreground',
                )}
              >
                {k === 'delta' ? 'Δ parent' : k}
              </button>
            ))}
          </div>
        </div>
        <div className="scroll-x">
          <table className="w-full min-w-[760px] text-left text-[12px]">
            <thead className="eyebrow border-b border-border">
              <tr>
                <th className="px-3 py-2">iter</th>
                <th className="px-3 py-2">candidate</th>
                <th className="px-3 py-2">verdict</th>
                <th className="px-3 py-2">parent</th>
                <th className="px-3 py-2 text-right">val</th>
                <th className="px-3 py-2 text-right">Δ parent</th>
                <th className="px-3 py-2 text-right">tasks</th>
                <th className="px-3 py-2 text-right">eval $</th>
                <th className="px-3 py-2 text-right">opt time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((n) => (
                <tr key={n.id} className="hover:bg-surface-2">
                  <td className="tnum px-3 py-1.5 text-muted">{n.iteration ?? 0}</td>
                  <td className="px-3 py-1.5">
                    <span className="inline-flex items-center gap-1.5 font-mono">
                      {n.id === summary.best_id && (
                        <Star
                          size={11}
                          className="text-accent"
                          aria-label="best candidate"
                          fill="currentColor"
                        />
                      )}
                      {n.id}
                    </span>
                    {n.merge_of && n.merge_of.length > 0 && (
                      <span className="ml-1.5 text-[10px] text-muted">
                        merge of {n.merge_of.join(' + ')}
                      </span>
                    )}
                    {n.epoch != null && (
                      <span className="ml-1.5 text-[10px] text-muted">epoch {n.epoch}</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5">
                    <VerdictBadge verdict={n.status} />
                  </td>
                  <td className="px-3 py-1.5 font-mono text-muted">{n.parent ?? '—'}</td>
                  <td className="tnum px-3 py-1.5 text-right">
                    {n.val == null ? (
                      <span className="text-muted" title="No valid measurement exists.">
                        —
                      </span>
                    ) : (
                      pct(n.val)
                    )}
                  </td>
                  <td
                    className={cn(
                      'tnum px-3 py-1.5 text-right',
                      n.delta == null
                        ? 'text-muted'
                        : n.delta > 0
                          ? 'text-accepted'
                          : n.delta < 0
                            ? 'text-rejected'
                            : 'text-muted',
                    )}
                  >
                    {n.delta == null ? '—' : `${n.delta > 0 ? '+' : ''}${n.delta.toFixed(3)}`}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {Object.keys(n.per_task ?? {}).length || '—'}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {n.cost_usd ? usd(n.cost_usd) : '—'}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {n.optimizer_seconds ? duration(n.optimizer_seconds) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="border-t border-border px-3.5 py-2 text-[11px] text-muted">
          val is the selection metric. A "—" is a measurement that does not exist, never a
          zero.
        </p>
      </Card>
    </div>
  )
}
