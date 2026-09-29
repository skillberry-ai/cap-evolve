import type { GraphNode, GateDecision, PerIterationCost } from '../lib/types'

interface OptimizerStoryProps {
  nodes: GraphNode[]
  gates: GateDecision[]
  perIteration: PerIterationCost[]
  onIterationClick?: (iteration: number) => void
}

export function OptimizerStory({ nodes, gates, perIteration, onIterationClick }: OptimizerStoryProps) {
  // Group nodes by iteration
  const iterations = nodes
    .filter(n => n.iteration != null && n.iteration > 0)
    .sort((a, b) => (a.iteration || 0) - (b.iteration || 0))

  const formatPercent = (v: number | null | undefined) => {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`
  }

  const formatUsd = (v: number | null | undefined) => {
    return v == null ? '—' : `$${v.toFixed(2)}`
  }

  const formatDuration = (seconds: number | null | undefined) => {
    if (!seconds) return '—'
    const s = Math.round(seconds)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    return h ? `${h}h ${m}m` : `${m}m`
  }

  const getGate = (candidateId: string) => gates.find(g => g.candidate === candidateId)
  const getPerIter = (candidateId: string) => perIteration.find(p => p.candidate === candidateId)

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="text-left font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Iteration
            </th>
            <th className="text-left font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Candidate
            </th>
            <th className="text-left font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Diagnosis Summary
            </th>
            <th className="text-left font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Outcome
            </th>
            <th className="text-right font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Val Score
            </th>
            <th className="text-right font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Fixed / Broke
            </th>
            <th className="text-right font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Time
            </th>
            <th className="text-right font-semibold text-[var(--muted)] text-xs uppercase tracking-wider p-3">
              Cost
            </th>
          </tr>
        </thead>
        <tbody>
          {iterations.map(node => {
            const gate = getGate(node.id)
            const perIter = getPerIter(node.id)
            const diagnosis = node.diagnosis

            return (
              <tr
                key={node.id}
                className="border-b border-[var(--border)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer"
                onClick={() => onIterationClick?.(node.iteration!)}
              >
                <td className="p-3">
                  <span className="font-mono font-semibold">{node.iteration}</span>
                </td>

                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs">{node.id}</span>
                    {node.status === 'accepted' && (
                      <span className="px-1.5 py-0.5 text-[10px] rounded bg-[var(--accepted)] bg-opacity-20 text-[var(--accepted)] border border-[var(--accepted)] border-opacity-30">
                        ✓
                      </span>
                    )}
                    {node.status === 'rejected' && (
                      <span className="px-1.5 py-0.5 text-[10px] rounded bg-[var(--rejected)] bg-opacity-20 text-[var(--rejected)] border border-[var(--rejected)] border-opacity-30">
                        ✕
                      </span>
                    )}
                  </div>
                </td>

                <td className="p-3 max-w-md">
                  {diagnosis ? (
                    <div className="text-xs text-[var(--muted-strong)] line-clamp-2">
                      {diagnosis.headline || 'No headline'}
                      {diagnosis.clusters.length > 0 && (
                        <span className="ml-2 text-[var(--muted)]">
                          ({diagnosis.clusters.length} clusters, {diagnosis.edits.length} edits)
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-[var(--muted)]">No diagnosis</span>
                  )}
                </td>

                <td className="p-3">
                  {gate ? (
                    <div className="text-xs">
                      <div className="font-mono">
                        Δ {gate.delta != null ? (gate.delta >= 0 ? '+' : '') + gate.delta.toFixed(4) : '—'}
                      </div>
                      <div className="text-[var(--muted)] text-[10px]">
                        vs {gate.threshold?.toFixed(4) || '—'}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs text-[var(--muted)]">—</span>
                  )}
                </td>

                <td className="p-3 text-right">
                  <div className="font-mono font-semibold">{formatPercent(node.val)}</div>
                  {node.stderr != null && (
                    <div className="text-[10px] text-[var(--muted)] font-mono">
                      ± {node.stderr.toFixed(3)}
                    </div>
                  )}
                </td>

                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    {node.fixed && node.fixed.length > 0 && (
                      <span className="text-xs font-mono text-[var(--accepted)]">
                        +{node.fixed.length}
                      </span>
                    )}
                    {node.broke && node.broke.length > 0 && (
                      <span className="text-xs font-mono text-[var(--rejected)]">
                        -{node.broke.length}
                      </span>
                    )}
                    {(!node.fixed || node.fixed.length === 0) &&
                      (!node.broke || node.broke.length === 0) && (
                        <span className="text-xs text-[var(--muted)]">—</span>
                      )}
                  </div>
                </td>

                <td className="p-3 text-right">
                  <div className="font-mono text-xs">
                    {formatDuration(perIter?.optimizer_seconds)}
                  </div>
                  <div className="text-[10px] text-[var(--muted)] font-mono">
                    +{formatDuration(perIter?.runner_seconds)} eval
                  </div>
                </td>

                <td className="p-3 text-right">
                  <div className="font-mono text-xs font-semibold">
                    {formatUsd(perIter?.optimizer_usd)}
                  </div>
                  <div className="text-[10px] text-[var(--muted)] font-mono">
                    +{formatUsd(perIter?.runner_usd)} eval
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {iterations.length === 0 && (
        <div className="text-center py-8 text-sm text-[var(--muted)]">
          No iterations found
        </div>
      )}
    </div>
  )
}
