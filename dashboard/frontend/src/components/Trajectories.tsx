import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Wrench, XCircle, X } from 'lucide-react'
import { api } from '../lib/api'
import { pct } from '../lib/format'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { cn } from '../lib/cn'

/** Per-task rollouts, worst-first, with a detail drawer (trace + tools used). */
export function Trajectories({ runId }: { runId: string }) {
  const [split, setSplit] = useState<string>('val')
  const [openFile, setOpenFile] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['rollouts', runId, split],
    queryFn: ({ signal }) => api.rollouts(runId, split, signal),
  })

  const rows = useMemo(
    () => [...(data ?? [])].sort((a, b) => (a.reward ?? 0) - (b.reward ?? 0)),
    [data],
  )
  const splits = useMemo(() => {
    const s = new Set<string>(['val', 'test'])
    ;(data ?? []).forEach((r) => s.add(r.split))
    return [...s]
  }, [data])

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-medium">Trajectories</h3>
        <div className="ml-auto flex gap-1">
          {splits.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSplit(s)}
              className={cn(
                'rounded px-2 py-1 text-xs transition-colors',
                s === split ? 'bg-surface-2 text-foreground' : 'text-muted hover:text-foreground',
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}
      {data && rows.length === 0 && (
        <p className="py-8 text-center text-sm text-muted">No rollouts for “{split}”.</p>
      )}

      {rows.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-muted">
            <tr className="border-b border-border">
              <th className="py-1.5 pr-3 font-medium">task</th>
              <th className="py-1.5 pr-3 font-medium">candidate</th>
              <th className="py-1.5 pr-3 font-medium">reward</th>
              <th className="py-1.5 font-medium">feedback</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.file}
                onClick={() => setOpenFile(r.file)}
                className="cursor-pointer border-b border-border/60 hover:bg-surface-2"
              >
                <td className="py-1.5 pr-3">
                  <span className="inline-flex items-center gap-1.5">
                    <PassIcon reward={r.reward} />
                    {r.task_id}
                  </span>
                </td>
                <td className="py-1.5 pr-3 text-muted">{r.candidate}</td>
                <td className="tnum py-1.5 pr-3">{pct(r.reward)}</td>
                <td className="max-w-[28ch] truncate py-1.5 text-muted">{r.feedback || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openFile && <RolloutDrawer runId={runId} file={openFile} onClose={() => setOpenFile(null)} />}
    </Card>
  )
}

function PassIcon({ reward }: { reward: number | null }) {
  const pass = (reward ?? 0) >= 0.5
  return pass ? (
    <CheckCircle2 size={14} className="text-accepted" aria-label="pass" />
  ) : (
    <XCircle size={14} className="text-rejected" aria-label="fail" />
  )
}

function RolloutDrawer({ runId, file, onClose }: { runId: string; file: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['rollout', runId, file],
    queryFn: ({ signal }) => api.rollout(runId, file, signal),
  })
  const tools = data?.rollout?.tool_calls ?? []
  const toolCounts = tools.reduce<Record<string, number>>((acc, t) => {
    const n = String(t?.name ?? 'unknown')
    acc[n] = (acc[n] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button aria-label="Close" className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative h-full w-full max-w-xl overflow-y-auto border-l border-border bg-surface p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="font-mono text-sm">{file}</h4>
          <button onClick={onClose} aria-label="Close" className="text-muted hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        {isLoading && <Skeleton className="h-64 w-full" />}
        {data && (
          <div className="space-y-4 text-sm">
            <Field label="reward">
              <span className="tnum">{pct(data.score?.reward ?? null)}</span>
              {data.score?.feedback && <span className="ml-2 text-muted">{data.score.feedback}</span>}
            </Field>
            {Object.keys(toolCounts).length > 0 && (
              <Field label="tools used">
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(toolCounts).map(([n, c]) => (
                    <span key={n} className="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 text-xs">
                      <Wrench size={11} className="text-primary" />
                      {n} {c > 1 && <span className="tnum text-muted">×{c}</span>}
                    </span>
                  ))}
                </div>
              </Field>
            )}
            <Field label="input">
              <Pre>{stringify(data.input)}</Pre>
            </Field>
            <Field label="output">
              <Pre>{stringify(data.rollout?.output)}</Pre>
            </Field>
            {data.rollout?.trace && (
              <Field label="trace">
                <Pre>{String(data.rollout.trace)}</Pre>
              </Field>
            )}
            {data.rollout?.error && (
              <Field label="error">
                <Pre className="text-rejected">{String(data.rollout.error)}</Pre>
              </Field>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">{label}</div>
      {children}
    </div>
  )
}

function Pre({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <pre className={cn('max-h-60 overflow-auto rounded bg-background p-2 text-xs', className)}>
      {children}
    </pre>
  )
}

function stringify(v: unknown): string {
  if (v == null) return '—'
  if (typeof v === 'string') return v
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}
