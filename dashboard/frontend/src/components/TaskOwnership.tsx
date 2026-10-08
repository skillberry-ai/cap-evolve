import { useMemo } from 'react'
import type { GraphNode } from '../lib/types'
import { ownershipCandidates, computeOwnership, colorForIndex } from '../lib/ownership'
import { Card } from './ui/Card'

/**
 * Per-task ownership grid (issue #684 item 3/9) — which candidate currently best-scores
 * each task, GEPA's per-instance ownership idea (Algorithm 2) applied to our own
 * per-candidate per-task rewards. One cell per task, colored by its owning candidate
 * (ties shown as a split cell). This is a diversity/coverage view, distinct from the
 * reward+cost Pareto scatter above it on the Overview tab.
 */
export function TaskOwnership({ nodes }: { nodes: GraphNode[] }) {
  const candidates = useMemo(() => ownershipCandidates(nodes), [nodes])
  const ownership = useMemo(() => computeOwnership(candidates), [candidates])
  const colorOf = useMemo(() => {
    const m = new Map<string, string>()
    candidates.forEach((n, i) => m.set(n.id, colorForIndex(i)))
    return m
  }, [candidates])

  const taskIds = useMemo(
    () => Object.keys(ownership.owners).sort((a, b) => ownership.bestScore[b] - ownership.bestScore[a]),
    [ownership],
  )

  if (candidates.length < 2 || taskIds.length === 0) return null

  return (
    <Card className="overflow-hidden p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">Task ownership</h3>
        <span className="text-xs text-muted">which candidate best-scores each task</span>
      </div>
      <div className="flex flex-wrap gap-1">
        {taskIds.map((t) => {
          const owners = ownership.owners[t]
          const tied = owners.length > 1
          return (
            <div
              key={t}
              title={`${t}: best ${ownership.bestScore[t].toFixed(2)} — owned by ${owners.join(', ')}`}
              className="flex h-6 w-7 items-center justify-center rounded-[3px] text-[8px] text-white"
              style={{
                background: tied
                  ? `linear-gradient(90deg, ${owners.map((o) => colorOf.get(o)).join(', ')})`
                  : colorOf.get(owners[0]),
              }}
            >
              {tied ? '≈' : ''}
            </div>
          )
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        {candidates.map((n, i) => (
          <span key={n.id} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="h-2.5 w-2.5 rounded-sm"
              style={{ background: colorForIndex(i) }}
            />
            {n.id} <span className="tnum">({ownership.ownershipCount[n.id] ?? 0})</span>
          </span>
        ))}
      </div>
    </Card>
  )
}
