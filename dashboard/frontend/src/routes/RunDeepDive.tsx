import { useCallback, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api, LivePendingError } from '../lib/api'
import { useRunStream } from '../lib/useRunStream'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { Tabs, type TabDef } from '../components/ui/Tabs'
import { StatusBadge } from '../components/StatusBadge'
import { KpiStrip } from '../components/KpiStrip'
import { BestCurveChart } from '../components/BestCurveChart'
import { TaskHeatmap } from '../components/TaskHeatmap'
import { LineageTree } from '../components/LineageTree'
import { PhasesTimeline } from '../components/PhasesTimeline'
import { Trajectories } from '../components/Trajectories'
import { ChangesPanel } from '../components/ChangesPanel'
import { Insights } from '../components/Insights'
import { CostPanel } from '../components/CostPanel'
import type { RunStatus } from '../lib/types'

/**
 * #139 consolidated ten tabs into seven. The four overlapping file/diff surfaces
 * (Iterations · Git diffs · Memory · Files) are now sub-modes of `changes`; `overview`
 * became `fitness` and carries both candidate-selection charts, because those are the
 * sources of the cross-links rather than a tab spent on one chart.
 */
const TABS: TabDef[] = [
  { id: 'fitness', label: 'Fitness' },
  { id: 'cost', label: 'Cost' },
  { id: 'phases', label: 'Phases' },
  { id: 'lineage', label: 'Lineage' },
  { id: 'trajectories', label: 'Trajectories' },
  // Named for all four sub-modes, not just the diffs: Memory and Files were never diff
  // surfaces, so a label that says only "changes" hides them.
  { id: 'changes', label: 'Changes, memory & files' },
  { id: 'insights', label: 'Insights' },
]

export function RunDeepDive() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  // Tab + cross-link state lives in the URL, not component state: a cross-link must change
  // the tab AND what that tab shows in one navigation, the back button must undo it, and
  // "look at this candidate" should be a shareable link.
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? undefined
  const candidate = params.get('candidate')
  const focusTask = params.get('task')
  const focus = focusTask && candidate ? { task: focusTask, candidate } : null

  const goto = useCallback(
    (next: Record<string, string | null | undefined>) => {
      setParams((prev) => {
        const p = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(next)) {
          if (v == null) p.delete(k)
          else p.set(k, v)
        }
        return p
      })
    },
    [setParams],
  )

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run', id],
    queryFn: ({ signal }) => api.run(id!, signal),
    enabled: !!id,
    // A live-view run whose first snapshot hasn't landed yet 404s, not fails: settle
    // into isError immediately (no retry backoff) so the friendly message below shows
    // right away, then let refetchInterval poll every 10s until the poller's first
    // push lands and the fetch succeeds.
    retry: (failureCount, err) => (err instanceof LivePendingError ? false : failureCount < 3),
    refetchInterval: (query) => (query.state.error instanceof LivePendingError ? 10_000 : false),
  })
  const isLivePending = error instanceof LivePendingError

  // A stale or typo'd `?candidate` must not be *named* by the cross-link headers: the
  // panels below already fall back to a real candidate, so claiming the bad id would make
  // the page assert it is showing something it isn't.
  const knownCandidate =
    candidate && data?.graph.nodes.some((n) => n.id === candidate) ? candidate : null

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

        {isError && isLivePending && (
          <Card className="border-accent/40">
            <div className="p-4 text-sm text-muted">
              Hold on — this run just started. Live data will show up here in a few minutes,
              once the first snapshot is exported.
            </div>
          </Card>
        )}

        {isError && !isLivePending && (
          <Card className="border-rejected/40">
            <div className="p-4 text-sm text-rejected">Couldn’t load run: {(error as Error)?.message}</div>
          </Card>
        )}

        {data && (
          <div className="space-y-5">
            <KpiStrip summary={data.summary} />
            <Tabs
              tabs={tabs}
              label="Run views"
              value={tab}
              onChange={(next) => goto({ tab: next })}
            >
              {(active) =>
                active === 'fitness' ? (
                  <div className="space-y-4">
                    <BestCurveChart
                      nodes={data.graph.nodes}
                      // Cross-link: a candidate goes to its rollouts; its diff is one click
                      // further, preselected to the same id.
                      onSelect={(cid) => goto({ tab: 'trajectories', candidate: cid, task: null })}
                    />
                    <TaskHeatmap
                      nodes={data.graph.nodes}
                      tasks={data.summary.tasks ?? []}
                      // Cross-link: a cell opens that task's rollout drawer directly.
                      onOpenRollout={(task, cid) => goto({ tab: 'trajectories', candidate: cid, task })}
                    />
                  </div>
                ) : active === 'cost' ? (
                  <CostPanel summary={data.summary} />
                ) : active === 'phases' ? (
                  <PhasesTimeline detail={data} />
                ) : active === 'lineage' ? (
                  <LineageTree graph={data.graph} />
                ) : active === 'trajectories' ? (
                  <div className="space-y-3">
                    {knownCandidate && (
                      <button
                        type="button"
                        onClick={() => goto({ tab: 'changes', mode: 'candidate', task: null })}
                        className="rounded text-xs text-primary underline decoration-dotted underline-offset-2"
                      >
                        See what {knownCandidate} changed →
                      </button>
                    )}
                    <Trajectories
                      runId={id!}
                      candidate={candidate}
                      focus={focus}
                      onClearFocus={() => goto({ candidate: null, task: null })}
                      onCloseRollout={() => goto({ task: null })}
                    />
                  </div>
                ) : active === 'changes' ? (
                  <div className="space-y-3">
                    {knownCandidate && (
                      <button
                        type="button"
                        onClick={() => goto({ tab: 'trajectories', task: null })}
                        className="rounded text-xs text-primary underline decoration-dotted underline-offset-2"
                      >
                        ← See how {knownCandidate} scored per task
                      </button>
                    )}
                    {candidate && !knownCandidate && (
                      <p className="text-xs text-muted">
                        No candidate <span className="font-mono">{candidate}</span> in this run —
                        showing the newest one instead.
                      </p>
                    )}
                    <ChangesPanel
                      runId={id!}
                      graph={data.graph}
                      candidate={candidate}
                      mode={params.get('mode') ?? undefined}
                      onModeChange={(m) => goto({ mode: m })}
                    />
                  </div>
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
                      // sandbox it: allow scripts, its own-origin storage, and forms,
                      // but deny top-level navigation and popups. NOTE: allow-scripts +
                      // allow-same-origin only sandboxes while `customUrl` is a *different*
                      // origin than this dashboard (it is today — a separate localhost
                      // port). If a run ever points this at the dashboard's own origin,
                      // the frame could remove its own sandbox; keep custom views cross-origin.
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
