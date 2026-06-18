import { useQuery } from '@tanstack/react-query'
import { Ban, Lightbulb, TrendingUp, Wrench } from 'lucide-react'
import { api } from '../lib/api'
import type { RunDetail } from '../lib/types'
import { deadEnds, narrative, toolUsage, whatHelped } from '../lib/insights'
import { pct } from '../lib/format'
import { Card } from './ui/Card'

export function Insights({ runId, detail }: { runId: string; detail: RunDetail }) {
  const { data: memory } = useQuery({ queryKey: ['memory', runId], queryFn: ({ signal }) => api.memory(runId, signal) })
  const { data: rollouts } = useQuery({
    queryKey: ['rollouts', runId, undefined],
    queryFn: ({ signal }) => api.rollouts(runId, undefined, signal),
  })

  const helped = whatHelped(detail.graph)
  const ends = deadEnds(memory?.rejected ?? [])
  const diagnoses = (detail.summary.diagnoses ?? []) as Array<Record<string, unknown>>
  const warnings = (detail.summary.gate_warnings ?? []) as Array<Record<string, unknown>>

  // Tool usage needs full rollout details; fetch a few of the worst tasks lazily.
  const sample = (rollouts ?? []).slice(0, 6)
  const toolQueries = useQuery({
    queryKey: ['tooluse', runId, sample.map((r) => r.file)],
    enabled: sample.length > 0,
    queryFn: async ({ signal }) => {
      const details = await Promise.all(sample.map((r) => api.rollout(runId, r.file, signal).catch(() => null)))
      return toolUsage(details.filter(Boolean) as Parameters<typeof toolUsage>[0])
    },
  })
  const tools = toolQueries.data ?? []

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h3 className="mb-1 flex items-center gap-1.5 text-sm font-medium">
          <Lightbulb size={15} className="text-accent" /> Narrative
        </h3>
        <p className="text-sm text-muted">{narrative(detail)}</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-accepted">
            <TrendingUp size={15} /> What helped
          </h3>
          {helped.length === 0 && <p className="py-4 text-sm text-muted">No accepted improvements recorded.</p>}
          <ul className="space-y-1">
            {helped.map((h) => (
              <li key={h.id} className="flex items-center justify-between rounded bg-surface-2 px-2 py-1.5 text-sm">
                <span className="font-mono text-xs">{h.id}</span>
                <span className="tnum">
                  <span className="text-accepted">+{pct(h.delta)}</span>
                  <span className="ml-2 text-muted">→ {pct(h.val)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-rejected">
            <Ban size={15} /> What not to try
          </h3>
          {ends.length === 0 && <p className="py-4 text-sm text-muted">No dead-ends yet.</p>}
          <ul className="space-y-1">
            {ends.map((d, i) => (
              <li key={i} className="rounded bg-surface-2 px-2 py-1.5 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">{d.examples.join(', ')}</span>
                  {d.count > 1 && <span className="tnum text-xs text-rejected">×{d.count}</span>}
                </div>
                <div className="text-xs text-foreground/80">{d.reason}</div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
            <Wrench size={15} className="text-primary" /> Tool usage
          </h3>
          {tools.length === 0 && <p className="py-4 text-sm text-muted">No tool calls observed in sampled rollouts.</p>}
          <ul className="space-y-1">
            {tools.map((t) => (
              <li key={t.name} className="flex items-center justify-between rounded bg-surface-2 px-2 py-1.5 text-sm">
                <span className="font-mono text-xs">{t.name}</span>
                <span className="tnum text-muted">×{t.count}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <h3 className="mb-2 text-sm font-medium">Gate warnings & diagnoses</h3>
          {warnings.length === 0 && diagnoses.length === 0 && (
            <p className="py-4 text-sm text-muted">Clean run — no gate warnings or diagnoses.</p>
          )}
          <ul className="space-y-1 text-xs text-muted">
            {warnings.map((w, i) => (
              <li key={`w${i}`} className="rounded bg-surface-2 px-2 py-1.5">
                ⚠ {String(w.reason ?? JSON.stringify(w))}
              </li>
            ))}
            {diagnoses.map((d, i) => (
              <li key={`d${i}`} className="rounded bg-surface-2 px-2 py-1.5">
                {String(d.text ?? d.summary ?? JSON.stringify(d))}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
