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
import { GitCompareArrows } from 'lucide-react'
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
              <h3 className="mb-2 text-sm font-medium">Best-so-far over iterations</h3>
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
