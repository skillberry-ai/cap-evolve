import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { GraphNode, RunSummaryDetail } from '../lib/types'
import { getObjectives } from '../lib/objectives'
import { usd } from '../lib/format'
import { Card } from './ui/Card'

/** Each declared objective's own per-candidate field, when this run actually recorded
 * one — "reward" is `val` (every node has it), "cost" is `cost_usd` (the gate's own
 * default pareto objectives, gate.py's `_DEFAULT_PARETO_OBJECTIVES`), "tokens" is the
 * `tokens` field. A custom objective name this run never attached a node field for
 * (e.g. a bespoke secondary metric) has nothing to plot — returning null here is how
 * that objective is skipped below, never faked as a flat line. */
function accessorFor(name: string): ((n: GraphNode) => number | null) | null {
  if (name === 'reward') return (n) => n.val
  if (name === 'cost') return (n) => n.cost_usd ?? null
  if (name === 'tokens') return (n) => n.tokens ?? null
  return null
}

function formatFor(name: string, v: number): string {
  if (name === 'cost') return usd(v)
  if (name === 'reward') return `${Math.round(v * 100)}%`
  return String(v)
}

/** One small time-series per declared objective, plotted over iterations — the TREND
 * each objective took across candidates, distinct from the Pareto scatter's 2D
 * snapshot of where candidates currently sit (#676). Only rendered by the caller when
 * `isMultiObjective()` is true: a single-objective run already gets reward-over-time
 * from BestCurveChart and must not grow a second, redundant chart. */
export function ObjectiveTimeSeries({ nodes, summary }: { nodes: GraphNode[]; summary: RunSummaryDetail }) {
  const series = getObjectives(summary)
    .map((objective) => {
      const get = accessorFor(objective.name)
      if (!get) return null
      const points = [...nodes]
        .filter((n) => n.iteration != null && get(n) != null)
        .sort((a, b) => (a.iteration as number) - (b.iteration as number))
        .map((n) => ({ iteration: n.iteration as number, value: get(n) as number, id: n.id }))
      return points.length > 0 ? { objective, points } : null
    })
    .filter((s): s is NonNullable<typeof s> => s != null)

  if (series.length === 0) return null

  return (
    <Card className="p-4">
      <h3 className="mb-2 text-sm font-medium">Per-objective trend</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        {series.map(({ objective, points }) => (
          <div key={objective.name}>
            <div className="mb-1 text-xs text-muted">
              {objective.name} {objective.direction === 'minimize' ? '↓ minimize' : '↑ maximize'} over iterations
            </div>
            <div style={{ width: '100%', height: 140 }}>
              <ResponsiveContainer>
                <LineChart data={points} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="iteration" stroke="var(--muted)" tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis
                    stroke="var(--muted)"
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    width={36}
                    tickFormatter={(v: number) => formatFor(objective.name, v)}
                  />
                  <Tooltip
                    content={
                      <ObjectiveTooltip name={objective.name} />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

interface Point {
  iteration: number
  value: number
  id: string
}

function ObjectiveTooltip({
  name,
  active,
  payload,
}: {
  name: string
  active?: boolean
  payload?: Array<{ payload: Point }>
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs shadow-lg">
      <div className="font-medium">{p.id}</div>
      <div className="tnum text-muted">
        iteration {p.iteration} · {name} <span className="text-foreground">{formatFor(name, p.value)}</span>
      </div>
    </div>
  )
}
