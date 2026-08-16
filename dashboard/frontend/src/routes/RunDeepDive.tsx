import { useCallback, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api, LivePendingError } from '../lib/api'
import { useRunStream } from '../lib/useRunStream'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { Tabs, type TabDef } from '../components/ui/Tabs'
import { RunHeader } from '../components/RunHeader'
import { KpiStrip } from '../components/KpiStrip'
import { BestCurveChart } from '../components/BestCurveChart'
import { CandidatesPanel } from '../components/CandidatesPanel'
import { PhasesTimeline } from '../components/PhasesTimeline'
import { Trajectories } from '../components/Trajectories'
import { IterationsDiff } from '../components/IterationsDiff'
import { MemoryPanel } from '../components/MemoryPanel'
import { BudgetPanel } from '../components/CostPanel'
import { CostLedger } from '../components/CostLedger'
import { GatePanel } from '../components/GatePanel'
import { TaskMatrix } from '../components/TaskMatrix'
import { LogStream } from '../components/LogStream'
import {
  EvographPanel,
  FreeformPanel,
  GepaPanel,
  ScreensPanel,
  SkillOptPanel,
} from '../components/AlgoPanels'
import { FileTree } from '../components/FileTree'
import { GitDiff } from '../components/GitDiff'
import type { RunCapabilities, RunDetail } from '../lib/types'

/**
 * A run whose summary predates the `capabilities` map still has the DATA — infer from it.
 *
 * `capabilities` is the backend's answer to "which panels does this run have real data
 * for". An export written before that field existed answers nothing, and the UI then hid
 * the per-task heatmap and the diff tab on a run that carries per-task scores on every
 * node and a full git log. Absent still means omitted; this only asks the payload the
 * same question the backend would have. Trajectories are NOT inferred — rollouts live
 * behind a separate endpoint the UI cannot probe from here.
 */
function inferCapabilities(detail: RunDetail | undefined): RunCapabilities {
  const s = detail?.summary
  return {
    per_task: (detail?.graph.nodes ?? []).some((n) => n.per_task && Object.keys(n.per_task).length),
    diffs: !!s?.git_log?.length,
  } as RunCapabilities
}

/**
 * Tabs are built from what the run ACTUALLY RECORDED, not from which algorithm it is.
 *
 * The first block is true of every run — status, progress, candidates, gate decisions,
 * per-task outcomes, cost, logs, diffs, artifacts — and renders identically for
 * hill-climb, gepa, skillopt, evograph and agent-optimize. The second block is
 * per-algorithm and appears only when the corresponding capability is present, so a
 * missing signal means a missing tab, never an empty or fabricated one.
 */
export function buildTabs(caps: RunCapabilities | undefined, detail?: RunDetail): TabDef[] {
  const c = caps ?? inferCapabilities(detail)
  const tabs: TabDef[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'candidates', label: 'Candidates' },
    { id: 'gate', label: 'Gate' },
  ]
  if (c.per_task) tabs.push({ id: 'tasks', label: 'Tasks' })
  tabs.push({ id: 'cost', label: 'Cost' })
  tabs.push({ id: 'logs', label: 'Logs' })

  // Per-algorithm additions, behind a capability check.
  if (c.freeform) tabs.push({ id: 'rounds', label: 'Agent rounds' })
  if (c.screens) tabs.push({ id: 'screens', label: 'Screens' })
  if (c.gepa || c.minibatch) tabs.push({ id: 'gepa', label: 'GEPA' })
  if (c.skillopt || c.epochs) tabs.push({ id: 'skillopt', label: 'SkillOpt' })
  if (c.evograph) tabs.push({ id: 'evograph', label: 'Weakness graph' })

  if (c.diffs) tabs.push({ id: 'diffs', label: 'Diffs' })
  if (c.trajectories) tabs.push({ id: 'trajectories', label: 'Trajectories' })
  tabs.push({ id: 'memory', label: 'Memory' })
  tabs.push({ id: 'files', label: 'Files' })
  return tabs
}

export function RunDeepDive() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['run', id],
    queryFn: ({ signal }) => api.run(id!, signal),
    enabled: !!id,
    // A live-view run whose first snapshot hasn't landed yet 404s, not fails: settle
    // into isError immediately (no retry backoff) so the friendly message below shows
    // right away, then poll every 10s until the first push lands.
    retry: (failureCount, err) => (err instanceof LivePendingError ? false : failureCount < 3),
    refetchInterval: (query) => (query.state.error instanceof LivePendingError ? 10_000 : false),
  })
  const isLivePending = error instanceof LivePendingError

  // SSE: on each live event, debounce-refetch the authoritative reduced run.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onActivity = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ['run', id] })
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    }, 400)
  }, [id, queryClient])

  const stream = useRunStream(id, onActivity)
  const summary = data?.summary
  const tabs = buildTabs(summary?.capabilities, data)

  return (
    <AppShell live={summary?.status === 'running'}>
      <div className="mx-auto max-w-[1240px]">
        <Link
          to="/"
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft size={15} aria-hidden /> All runs
        </Link>

        {isLoading && (
          <div className="grid gap-3">
            <Skeleton className="h-9 w-64" />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
            <Skeleton className="h-72 w-full" />
          </div>
        )}

        {isError && isLivePending && (
          <Card className="border-primary/40">
            <div className="p-4 text-sm text-muted">
              This run just started. Its first snapshot has not been exported yet — this
              page polls every 10 seconds and will fill in on its own.
            </div>
          </Card>
        )}

        {isError && !isLivePending && (
          <Card className="border-rejected/40">
            <div className="p-4 text-sm text-rejected">
              Couldn’t load run: {(error as Error)?.message}
            </div>
          </Card>
        )}

        {data && summary && (
          <div className="space-y-5">
            <RunHeader
              runId={id!}
              summary={summary}
              liveEvents={stream.status === 'live' ? stream.count : 0}
            />
            <KpiStrip summary={summary} />
            <Tabs tabs={tabs}>{(active) => <TabBody active={active} data={data} runId={id!} />}</Tabs>
          </div>
        )}
      </div>
    </AppShell>
  )
}

function TabBody({ active, data, runId }: { active: string; data: RunDetail; runId: string }) {
  const s = data.summary
  const extra = s.algo_extra ?? {}
  switch (active) {
    case 'overview':
      return (
        <div className="space-y-5">
          <BestCurveChart nodes={data.graph.nodes} />
          <PhasesTimeline detail={data} />
        </div>
      )
    case 'candidates':
      return <CandidatesPanel graph={data.graph} summary={s} />
    case 'gate':
      return <GatePanel summary={s} nodes={data.graph.nodes} />
    case 'tasks':
      return <TaskMatrix summary={s} nodes={data.graph.nodes} />
    case 'cost':
      // The ledger already accounts for every dollar by phase; CostPanel is mounted only
      // for what it uniquely adds (budget meters + the evaluation-centric table). Its
      // by-role chart and per-iteration table restated the ledger and were dropped.
      return (
        <div className="space-y-5">
          <CostLedger summary={s} />
          <BudgetPanel summary={s} />
        </div>
      )
    case 'logs':
      return <LogStream log={s.log ?? []} />
    case 'rounds':
      return <FreeformPanel summary={s} nodes={data.graph.nodes} />
    case 'screens':
      return <ScreensPanel screens={extra.screens ?? []} nodes={data.graph.nodes} />
    case 'gepa':
      return <GepaPanel extra={extra} nodes={data.graph.nodes} />
    case 'skillopt':
      return <SkillOptPanel extra={extra} nodes={data.graph.nodes} />
    case 'evograph':
      return <EvographPanel extra={extra} />
    case 'diffs':
      return <IterationsDiff runId={runId} graph={data.graph} />
    case 'trajectories':
      return <Trajectories runId={runId} />
    case 'memory':
      return (
        <div className="space-y-5">
          <MemoryPanel runId={runId} graph={data.graph} />
          <GitDiff runId={runId} />
        </div>
      )
    case 'files':
      return <FileTree runId={runId} />
    default:
      return (
        <Card>
          <div className="p-8 text-center text-sm text-muted">Unknown view.</div>
        </Card>
      )
  }
}
