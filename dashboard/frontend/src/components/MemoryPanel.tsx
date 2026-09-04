import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, CheckCircle2, FileText, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import type { RunGraph, RunSummaryDetail } from '../lib/types'
import { pct } from '../lib/format'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'

/** Run-level optimizer narrative — JOURNAL/INSIGHTS/META_INSIGHTS/FRAMEWORK_IMPROVEMENTS
 * plus the best candidate's PROCESS.md. A file still holding its unedited seed template
 * (no real entry ever appended) is flagged rather than presented as real narrative. */
export function NarrativePanel({ summary }: { summary: RunSummaryDetail }) {
  const files = summary.narrative?.files ?? []
  if (!files.length) return null
  return (
    <Card className="p-4">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
        <BookOpen size={15} className="text-primary" /> Process narrative
      </h3>
      <div className="divide-y divide-border">
        {files.map((f, i) => (
          <details key={f.name} open={i === 0} className="py-1.5">
            <summary className="cursor-pointer font-mono text-xs text-muted hover:text-foreground">
              {f.title}
              {f.template_only && (
                <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
                  unedited template — no entry appended
                </span>
              )}
            </summary>
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">
              {f.text}
            </pre>
          </details>
        ))}
      </div>
    </Card>
  )
}

/** Optimizer memory: accepted history, rejected candidates (an audit trail — the core
 * does not re-read it to avoid re-proposing), and the
 * per-candidate snapshot files (PROCESS.md explainability / INSTRUCTIONS.md / the
 * capability files). */
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
  // One collapsible per file, first one open. Dumping every snapshot file inline made
  // this panel a ~2000px wall of optimizer prompt text with the capability file — the
  // one thing a reader came for — somewhere below the fold.
  return (
    <div className="divide-y divide-border">
      {data.map((f, i) => (
        <details key={f.name} open={i === 0} className="py-1.5">
          <summary className="cursor-pointer font-mono text-xs text-muted hover:text-foreground">
            {f.name}{' '}
            <span className="tnum text-[10px]">
              ({f.text.split('\n').length} lines)
            </span>
          </summary>
          <pre className="mt-1 max-h-72 overflow-auto rounded bg-background p-2 text-xs">
            {f.text}
          </pre>
        </details>
      ))}
    </div>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>
}
