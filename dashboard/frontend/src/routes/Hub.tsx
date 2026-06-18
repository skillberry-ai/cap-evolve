import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ArrowUpRight, GitCompareArrows, Inbox } from 'lucide-react'
import { api } from '../lib/api'
import type { RunSummary } from '../lib/types'
import { pct, signedPct, usd, deltaTone } from '../lib/format'
import { fadeUpItem, staggerContainer } from '../lib/motion'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { cn } from '../lib/cn'

const TONE_CLASS = { up: 'text-accepted', down: 'text-rejected', flat: 'text-muted' } as const

export function Hub() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['runs'],
    queryFn: ({ signal }) => api.runs(signal),
    refetchInterval: 4000, // keep the hub fresh; live runs update without reload
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const hasLive = !!data?.some((r) => r.status === 'live')

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  // Live runs first, then most-recent.
  const runs = [...(data ?? [])].sort((a, b) => {
    if (a.status === 'live' && b.status !== 'live') return -1
    if (b.status === 'live' && a.status !== 'live') return 1
    return b.mtime - a.mtime
  })

  return (
    <AppShell live={hasLive}>
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
            <p className="text-sm text-muted">Every optimization run — select two or more to compare.</p>
          </div>
          {selected.size >= 2 && (
            <Link
              to={`/compare?ids=${[...selected].join(',')}`}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white shadow-glow-primary transition-transform duration-150 active:scale-[0.97]"
            >
              <GitCompareArrows size={16} aria-hidden />
              Compare {selected.size}
            </Link>
          )}
        </div>

        {isLoading && (
          <div className="grid gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        )}

        {isError && (
          <Card className="border-rejected/40">
            <div className="p-4 text-sm text-rejected">
              Couldn’t load runs: {(error as Error)?.message}. Is the backend running on :7878?
            </div>
          </Card>
        )}

        {data && runs.length === 0 && (
          <Card>
            <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
              <Inbox className="text-muted" aria-hidden />
              <p className="font-medium">No runs yet</p>
              <p className="max-w-sm text-sm text-muted">
                Run <code className="tnum text-foreground">cap-evolve run</code> — the dashboard fills
                in live as candidates are evaluated.
              </p>
            </div>
          </Card>
        )}

        {data && runs.length > 0 && (
          <motion.ul
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="grid gap-3"
          >
            {runs.map((r) => (
              <motion.li key={r.run_id} variants={fadeUpItem}>
                <RunRow run={r} selected={selected.has(r.run_id)} onToggle={() => toggle(r.run_id)} />
              </motion.li>
            ))}
          </motion.ul>
        )}
      </div>
    </AppShell>
  )
}

function RunRow({
  run,
  selected,
  onToggle,
}: {
  run: RunSummary
  selected: boolean
  onToggle: () => void
}) {
  const tone = deltaTone(run.delta_pct)
  return (
    <Card
      className={cn(
        'flex items-center gap-4 p-4 hover:border-primary/50',
        selected && 'border-primary/70 bg-surface-2',
      )}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={onToggle}
        aria-label={`Select ${run.run_id} for comparison`}
        className="h-5 w-5 shrink-0 accent-[var(--primary)]"
      />
      <Link to={`/runs/${run.run_id}`} className="flex min-w-0 flex-1 items-center gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium">{run.run_id}</span>
            {run.algorithm && (
              <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted">
                {run.algorithm}
              </span>
            )}
          </div>
          <StatusBadge status={run.status} className="mt-1" />
        </div>

        <Metric label="best" value={pct(run.best_val)} accent />
        <Metric
          label="Δ"
          value={signedPct(run.delta_pct)}
          className={TONE_CLASS[tone]}
        />
        <Metric label="iters" value={String(run.iterations)} />
        <Metric label="cost" value={usd(run.total_usd)} hideOnSm />
        <ArrowUpRight size={16} className="shrink-0 text-muted" aria-hidden />
      </Link>
    </Card>
  )
}

function Metric({
  label,
  value,
  accent,
  className,
  hideOnSm,
}: {
  label: string
  value: string
  accent?: boolean
  className?: string
  hideOnSm?: boolean
}) {
  return (
    <div className={cn('w-16 text-right', hideOnSm && 'hidden sm:block')}>
      <div className={cn('tnum text-sm', accent ? 'text-accent' : 'text-foreground', className)}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
    </div>
  )
}
