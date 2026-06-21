import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, FileText, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { RunGraph } from '../lib/types'
import { pct } from '../lib/format'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'

/** Optimizer memory: accepted history, rejected ("do-not-re-propose"), and the
 * per-candidate scratch files (MEMORY.md / STATE.md / INSTRUCTIONS.md / prompt). */
export function MemoryPanel({ runId, graph }: { runId: string; graph: RunGraph }) {
  const { data, isLoading } = useQuery({
    queryKey: ['memory', runId],
    queryFn: ({ signal }) => api.memory(runId, signal),
  })

  const candidateIds = useMemo(
    () => graph.nodes.map((n) => n.id).filter((id) => id !== graph.root || id === 'seed'),
    [graph],
  )
  const [cid, setCid] = useState<string>(graph.best_id ?? graph.nodes[0]?.id ?? 'seed')

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-accepted">
            <CheckCircle2 size={15} /> Accepted history
          </h3>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {data && data.history.length === 0 && <Empty>No accepted candidates yet.</Empty>}
          <ul className="space-y-1.5">
            {data?.history.map((h, i) => (
              <li key={i} className="rounded bg-surface-2 px-2 py-1.5 text-sm">
                <span className="font-mono text-xs text-muted">{h.candidate_id}</span>
                <span className="tnum ml-2 text-accent">{pct(h.val)}</span>
                <div className="text-xs text-muted">{h.summary}</div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-rejected">
            <XCircle size={15} /> Rejected memory
          </h3>
          {isLoading && <Skeleton className="h-24 w-full" />}
          {data && data.rejected.length === 0 && <Empty>Nothing rejected.</Empty>}
          <ul className="space-y-1.5">
            {data?.rejected.map((r, i) => (
              <li key={i} className="rounded bg-surface-2 px-2 py-1.5 text-sm">
                <span className="font-mono text-xs text-muted">{r.candidate_id}</span>
                <div className="text-xs text-muted">{r.summary}</div>
                <div className="mt-0.5 text-xs text-rejected/90">{r.reason}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-medium">
            <FileText size={15} className="text-primary" /> Candidate scratch
          </h3>
          <select
            value={cid}
            onChange={(e) => setCid(e.target.value)}
            className="ml-auto rounded border border-border bg-surface-2 px-2 py-1 text-sm"
            aria-label="candidate"
          >
            {candidateIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
        <CandidateFiles runId={runId} cid={cid} />
      </Card>
    </div>
  )
}

function CandidateFiles({ runId, cid }: { runId: string; cid: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['candidate-files', runId, cid],
    queryFn: ({ signal }) => api.candidateFiles(runId, cid, signal),
  })
  if (isLoading) return <Skeleton className="h-40 w-full" />
  if (!data || data.length === 0) return <Empty>No snapshot files for {cid}.</Empty>
  return (
    <div className="space-y-3">
      {data.map((f) => (
        <div key={f.name}>
          <div className="mb-1 font-mono text-xs text-muted">{f.name}</div>
          <pre className="max-h-60 overflow-auto rounded bg-background p-2 text-xs">{f.text}</pre>
        </div>
      ))}
    </div>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>
}
