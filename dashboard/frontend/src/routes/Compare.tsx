import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AlertTriangle, GitCompareArrows } from 'lucide-react'
import { api } from '../lib/api'
import type { CompareRow } from '../lib/types'
import { pct, signedPct, usd, deltaTone } from '../lib/format'
import { AppShell } from '../components/AppShell'
import { Card } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'

const SERIES_COLORS = ['#3b82f6', '#f59e0b', '#22c55e', '#a855f7', '#ec4899', '#14b8a6']
const TONE = { up: 'text-accepted', down: 'text-rejected', flat: 'text-muted' } as const

export function Compare() {
  const [params] = useSearchParams()
  const ids = useMemo(() => (params.get('ids') ?? '').split(',').filter(Boolean), [params])

  const { data, isLoading } = useQuery({
    queryKey: ['compare', ids],
    queryFn: ({ signal }) => api.compare(ids, signal),
    enabled: ids.length > 0,
  })

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="mb-1 flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <GitCompareArrows size={22} className="text-primary" /> Compare runs
        </h1>
        <p className="mb-5 text-sm text-muted">
          {ids.length ? ids.join(' · ') : 'Select runs from the Hub to compare.'}
        </p>

        {ids.length === 0 && (
          <Card>
            <div className="px-4 py-12 text-center text-sm text-muted">
              No runs selected. <Link to="/" className="text-primary underline">Go to the Hub</Link> and pick two or more.
            </div>
          </Card>
        )}

        {isLoading && <Skeleton className="h-64 w-full" />}

        {data && data.runs.length > 0 && (
          <div className="space-y-5">
            <SplitMismatch runs={data.runs} />
            <Card className="overflow-x-auto p-4">
              <table className="w-full text-left text-sm">
                <thead className="text-muted">
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium">run</th>
                    <th className="py-2 pr-4 font-medium">algorithm</th>
                    <th className="py-2 pr-4 font-medium">baseline</th>
                    <th className="py-2 pr-4 font-medium">best</th>
                    <th className="py-2 pr-4 font-medium">Δ</th>
                    <th className="py-2 pr-4 font-medium">test</th>
                    <th className="py-2 pr-4 font-medium">iters</th>
                    <th className="py-2 font-medium">cost</th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.map((r, i) => (
                    <RunRow key={r.run_id} run={r} color={SERIES_COLORS[i % SERIES_COLORS.length]} />
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="p-4">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">Best-so-far over iterations</h3>
                {data.runs.some((r) => r.series.length <= 1) && (
                  <span className="text-xs text-muted">
                    {data.runs
                      .filter((r) => r.series.length <= 1)
                      .map((r) => r.run_id)
                      .join(', ')}{' '}
                    scored no candidate yet — baseline point only, no curve
                  </span>
                )}
              </div>
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  <LineChart margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      type="number"
                      dataKey="iteration"
                      stroke="var(--muted)"
                      tick={{ fontSize: 11 }}
                      allowDuplicatedCategory={false}
                    />
                    <YAxis domain={[0, 1]} stroke="var(--muted)" tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v * 100)}`} />
                    <Tooltip
                      contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      formatter={(value) => pct(Number(value))}
                    />
                    {data.runs.map((r, i) => (
                      <Line
                        key={r.run_id}
                        type="stepAfter"
                        data={r.series}
                        dataKey="best_so_far"
                        name={r.run_id}
                        stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  )
}

/**
 * Two runs are only comparable when their numbers are means over the SAME tasks.
 * Putting a 2-task toy run in one table and one chart with a 12-task benchmark run —
 * which the Hub happily lets you select — makes a meaningless comparison look rigorous,
 * so the mismatch is stated before the numbers, not buried in a tooltip.
 */
function SplitMismatch({ runs }: { runs: CompareRow[] }) {
  const withTasks = runs.filter((r) => (r.tasks?.length ?? 0) > 0)
  const key = (r: CompareRow) => [...(r.tasks ?? [])].sort().join('|')
  const distinct = new Set(withTasks.map(key))
  if (distinct.size < 2) return null
  return (
    <Card className="border-accent/40 bg-accent/[0.04]">
      <div className="flex gap-2.5 p-3.5">
        <AlertTriangle size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
        <p className="text-[12px] leading-relaxed text-muted-strong">
          <span className="font-medium text-accent">Different val splits.</span> These runs
          were scored on different task sets (
          {withTasks.map((r) => `${r.run_id}: ${r.tasks?.length ?? 0} tasks`).join(' · ')}
          ), so their scores are means over different work. Compare the shape of each
          run's progress, not the absolute numbers against each other.
        </p>
      </div>
    </Card>
  )
}

function RunRow({ run, color }: { run: CompareRow; color: string }) {
  const tone = deltaTone(run.delta_pct)
  return (
    <tr className="border-b border-border/60">
      <td className="py-2 pr-4">
        <Link to={`/runs/${run.run_id}`} className="inline-flex items-center gap-2 hover:text-primary">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {run.run_id}
        </Link>
      </td>
      <td className="py-2 pr-4 text-muted">{run.algorithm ?? '—'}</td>
      <td className="tnum py-2 pr-4">{pct(run.baseline_val)}</td>
      <td className="tnum py-2 pr-4 text-accent">{pct(run.best_val)}</td>
      <td className={cn('tnum py-2 pr-4', TONE[tone])}>{signedPct(run.delta_pct)}</td>
      <td className="tnum py-2 pr-4">{pct(run.test_reward)}</td>
      <td className="tnum py-2 pr-4">{run.iterations}</td>
      <td className="tnum py-2">{usd(run.total_usd)}</td>
    </tr>
  )
}
