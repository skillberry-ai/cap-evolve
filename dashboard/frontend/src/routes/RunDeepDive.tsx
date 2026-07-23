import { useCallback, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import { useRunStream } from '../lib/useRunStream'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { Tabs, type TabDef } from '../components/ui/Tabs'
import { StatusBadge } from '../components/StatusBadge'
import { KpiStrip } from '../components/KpiStrip'
import { BestCurveChart } from '../components/BestCurveChart'
import { LineageTree } from '../components/LineageTree'
import { PhasesTimeline } from '../components/PhasesTimeline'
import { Trajectories } from '../components/Trajectories'
import { IterationsDiff } from '../components/IterationsDiff'
import { MemoryPanel } from '../components/MemoryPanel'
import { Insights } from '../components/Insights'
import { CostPanel } from '../components/CostPanel'
import { FileTree } from '../components/FileTree'
import { GitDiff } from '../components/GitDiff'
import type { RunStatus } from '../lib/types'

const TABS: TabDef[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'cost', label: 'Cost' },
  { id: 'phases', label: 'Phases' },
  { id: 'lineage', label: 'Lineage' },
  { id: 'trajectories', label: 'Trajectories' },
  { id: 'iterations', label: 'Iterations' },
  { id: 'git', label: 'Git diffs' },
  { id: 'memory', label: 'Memory' },
  { id: 'files', label: 'Files' },
  { id: 'insights', label: 'Insights' },
]

export function RunDeepDive() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run', id],
    queryFn: ({ signal }) => api.run(id!, signal),
    enabled: !!id,
  })

  // Optional algorithm-shipped custom view (e.g. evo-graph's weakness graph),
  // mounted as an extra iframe tab when the run declares one. Absent -> no tab.
  const { data: customView } = useQuery({
    queryKey: ['custom-view', id],
    queryFn: ({ signal }) => api.customView(id!, signal),
    enabled: !!id,
    retry: false,
  })
  const customUrl = customView?.url
  const tabs: TabDef[] = customUrl
    ? [...TABS, { id: 'custom', label: customView?.title || 'Custom view' }]
    : TABS

  // SSE: on each live event, debounce-refetch the authoritative reduced run.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onActivity = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ['run', id] })
      queryClient.invalidateQueries({ queryKey: ['runs'] })
      // A run can declare (or update) its custom view mid-flight — refetch so the
      // extra tab appears/updates live rather than only after a full reload.
      queryClient.invalidateQueries({ queryKey: ['custom-view', id] })
    }, 400)
  }, [id, queryClient])

  const stream = useRunStream(id, onActivity)
  const liveStatus: RunStatus =
    stream.status === 'live' ? 'live' : stream.status === 'idle' || stream.status === 'done' ? 'done' : 'live'

  return (
    <AppShell live={stream.status === 'live'}>
      <div className="mx-auto max-w-6xl">
        <Link to="/" className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground">
          <ArrowLeft size={15} aria-hidden /> All runs
        </Link>

        <div className="mb-5 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{id}</h1>
          {data && <StatusBadge status={data.summary.test_reward != null ? 'done' : liveStatus} />}
          {data?.summary.algorithm && (
            <span className="rounded bg-surface-2 px-2 py-0.5 text-xs text-muted">{data.summary.algorithm}</span>
          )}
          {stream.status === 'live' && (
            <span className="tnum ml-auto text-xs text-muted">{stream.count} live events</span>
          )}
        </div>

        {isLoading && (
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
            <Skeleton className="h-72 w-full" />
          </div>
        )}

        {isError && (
          <Card className="border-rejected/40">
            <div className="p-4 text-sm text-rejected">Couldn’t load run: {(error as Error)?.message}</div>
          </Card>
        )}

        {data && (
          <div className="space-y-5">
            <KpiStrip summary={data.summary} />
            <Tabs tabs={tabs}>
              {(active) =>
                active === 'overview' ? (
                  <BestCurveChart nodes={data.graph.nodes} />
                ) : active === 'cost' ? (
                  <CostPanel summary={data.summary} />
                ) : active === 'phases' ? (
                  <PhasesTimeline detail={data} />
                ) : active === 'lineage' ? (
                  <LineageTree graph={data.graph} />
                ) : active === 'trajectories' ? (
                  <Trajectories runId={id!} />
                ) : active === 'iterations' ? (
                  <IterationsDiff runId={id!} graph={data.graph} />
                ) : active === 'git' ? (
                  <GitDiff runId={id!} />
                ) : active === 'memory' ? (
                  <MemoryPanel runId={id!} graph={data.graph} />
                ) : active === 'files' ? (
                  <FileTree runId={id!} />
                ) : active === 'insights' ? (
                  <Insights runId={id!} detail={data} />
                ) : active === 'custom' && customUrl ? (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center justify-end">
                      <a
                        href={customUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-bg hover:text-fg"
                        title={`Open ${customView?.title || 'this view'} full-screen in a new tab`}
                      >
                        Open full view in new window
                        <span aria-hidden="true">↗</span>
                      </a>
                    </div>
                    <iframe
                      src={customUrl}
                      title={customView?.title || 'Custom view'}
                      // The embedded page is data-driven (declared by the run dir), so
                      // sandbox it: allow it to run scripts and talk to its own origin,
                      // but deny top-level navigation, popups, and same-origin trust.
                      sandbox="allow-scripts allow-same-origin allow-forms"
                      referrerPolicy="no-referrer"
                      loading="lazy"
                      className="h-[80vh] w-full rounded-lg border border-border bg-surface"
                    />
                  </div>
                ) : (
                  <Card>
                    <div className="p-8 text-center text-sm text-muted">Unknown view.</div>
                  </Card>
                )
              }
            </Tabs>
          </div>
        )}
      </div>
    </AppShell>
  )
}
