import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { GitCommit as GitCommitIcon } from 'lucide-react'
import { api } from '../lib/api'
import { staggerContainer, fadeUpItem } from '../lib/motion'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { cn } from '../lib/cn'

const ROW_CLASS = {
  add: 'bg-accepted/10 text-accepted',
  del: 'bg-rejected/10 text-rejected',
  hunk: 'text-primary',
  ctx: 'text-muted',
} as const

/** Real git diffs between iteration commits from the run's git store. Pick a commit
 * to see what changed versus the previous one — the actual on-disk artifact history,
 * complementing the per-candidate snapshot diff. */
export function GitDiff({ runId }: { runId: string }) {
  const { data: log, isLoading } = useQuery({
    queryKey: ['gitlog', runId],
    queryFn: ({ signal }) => api.gitLog(runId, signal),
  })

  // Default selection = newest commit (diffed against its parent).
  const [sel, setSel] = useState<string | null>(null)
  useEffect(() => {
    if (log && log.length && sel === null) setSel(log[log.length - 1].hash)
  }, [log, sel])

  const idx = useMemo(() => (log ?? []).findIndex((c) => c.hash === sel), [log, sel])
  const hasParent = idx > 0
  const from = hasParent ? `${sel}~1` : null
  const to = sel

  const { data: diff, isLoading: diffLoading } = useQuery({
    queryKey: ['gitdiff', runId, from, to],
    queryFn: ({ signal }) => api.gitDiff(runId, from!, to!, signal),
    enabled: !!from && !!to,
  })

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!log || log.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No git history — this run’s store isn’t git (or git is unavailable).
        </div>
      </Card>
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
      <Card className="p-3">
        <h3 className="mb-2 px-1 text-sm font-medium">Iteration commits</h3>
        <motion.ol variants={staggerContainer} initial="hidden" animate="show" className="relative space-y-0.5">
          {[...log].reverse().map((c) => (
            <motion.li key={c.hash} variants={fadeUpItem}>
              <button
                type="button"
                onClick={() => setSel(c.hash)}
                className={cn(
                  'flex w-full items-start gap-2 rounded px-2 py-1.5 text-left hover:bg-surface-2',
                  sel === c.hash && 'bg-surface-2',
                )}
              >
                <GitCommitIcon size={14} className={cn('mt-0.5 shrink-0', sel === c.hash ? 'text-accent' : 'text-muted')} />
                <span className="min-w-0">
                  <span className="block truncate text-xs">{c.subject}</span>
                  <span className="tnum font-mono text-[10px] text-muted">{c.hash}</span>
                </span>
              </button>
            </motion.li>
          ))}
        </motion.ol>
      </Card>

      <Card className="p-3">
        {!hasParent ? (
          <p className="py-12 text-center text-sm text-muted">Initial commit — no previous iteration to diff against.</p>
        ) : diffLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : !diff || diff.files.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted">No file changes in this commit.</p>
        ) : (
          diff.files.map((f) => (
            <div key={f.path} className="mb-4">
              <div className="flex items-center gap-2 border-b border-border pb-1">
                <span className="truncate font-mono text-xs">{f.path}</span>
                <span className="tnum ml-auto text-xs text-accepted">+{f.added}</span>
                <span className="tnum text-xs text-rejected">−{f.removed}</span>
              </div>
              <pre className="overflow-x-auto rounded-b bg-background text-xs leading-relaxed">
                {f.rows.map((r, i) => (
                  <div key={i} className={cn('px-2', ROW_CLASS[r.t])}>
                    {r.l || ' '}
                  </div>
                ))}
              </pre>
            </div>
          ))
        )}
      </Card>
    </div>
  )
}
