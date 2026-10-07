import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { GraphNode, RunSummaryDetail } from '../lib/types'
import { toParetoPoints, paretoFrontier, type ParetoPoint } from '../lib/pareto'
import { pct, usd } from '../lib/format'
import { Card } from './ui/Card'

/** True only when the run's own config declares 2+ objectives — issue #665 is explicit
 * that single-objective runs keep today's simple UX (no Pareto chart, no note implying
 * multi-objective machinery that isn't there). `objectives` isn't a recognized
 * capevolve.yaml key yet (see dashboard.py's `_CONFIG_KEY_GROUPS`), so it currently
 * surfaces under the "Other" group — read generically across every group instead of
 * assuming where it lands. Checks raw array length, not shape: `getObjectives` (lib/
 * objectives.ts) additionally validates each entry's shape for display, which a plain
 * string list (an older/looser spec) would fail — this check must not regress on that. */
export function isMultiObjective(summary: RunSummaryDetail | undefined): boolean {
  const groups = summary?.config?.spec_groups ?? []
  for (const g of groups) {
    for (const item of g.items) {
      if (item.key === 'objectives' && Array.isArray(item.value) && item.value.length > 1) {
        return true
      }
    }
  }
  return false
}

const COLOR: Record<GraphNode['status'], string> = {
  seed: 'var(--seed)',
  accepted: 'var(--accepted)',
  rejected: 'var(--rejected)',
  indecisive: 'var(--indecisive)',
  failed: 'var(--failed)',
  screened: 'var(--muted)',
}

/** Reward (val) vs cost scatter: baseline + every candidate, non-dominated points
 * (the current Pareto frontier) drawn as filled stars, dominated points as plain dots.
 * Only rendered by the caller when `isMultiObjective()` is true. */
export function ParetoScatter({ nodes }: { nodes: GraphNode[] }) {
  const points = toParetoPoints(nodes)
  if (points.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No candidates with both a cost and a val score yet.
        </div>
      </Card>
    )
  }
  const frontier = paretoFrontier(points)
  const frontierPts = points.filter((p) => frontier.has(p.id))
  const dominatedPts = points.filter((p) => !frontier.has(p.id))

  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">Reward vs cost (Pareto)</h3>
        <span className="text-xs text-muted">
          {frontierPts.length} on the current frontier · {dominatedPts.length} dominated
        </span>
      </div>
      <div style={{ width: '100%', height: 280 }}>
        <ScatterChartWrap frontierPts={frontierPts} dominatedPts={dominatedPts} />
      </div>
    </Card>
  )
}

function ScatterChartWrap({
  frontierPts,
  dominatedPts,
}: {
  frontierPts: ParetoPoint[]
  dominatedPts: ParetoPoint[]
}) {
  return (
    <ResponsiveContainer>
      <ScatterChart margin={{ top: 8, right: 12, bottom: 24, left: 8 }}>
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="cost"
          type="number"
          name="cost"
          stroke="var(--muted)"
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => usd(v)}
          label={{ value: 'cost ($)', position: 'insideBottom', offset: -4, fontSize: 10, fill: 'var(--muted)' }}
        />
        <YAxis
          dataKey="reward"
          type="number"
          name="reward"
          domain={[0, 1]}
          stroke="var(--muted)"
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
        />
        <Tooltip content={<ParetoTooltip />} />
        <Scatter data={dominatedPts} fill="var(--muted)" shape="circle" />
        <Scatter data={frontierPts} shape={(p: unknown) => <FrontierDot {...(p as DotProps)} />} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

interface DotProps {
  cx?: number
  cy?: number
  payload?: ParetoPoint
}

function FrontierDot({ cx, cy, payload }: DotProps) {
  if (cx == null || cy == null || !payload) return null
  return <circle cx={cx} cy={cy} r={5.5} fill={COLOR[payload.status]} stroke="var(--accent)" strokeWidth={2} />
}

function ParetoTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ParetoPoint }> }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs shadow-lg">
      <div className="font-medium">{p.id}</div>
      <div className="tnum text-muted">
        reward <span className="text-foreground">{pct(p.reward)}</span> · cost{' '}
        <span className="text-foreground">{usd(p.cost)}</span>
      </div>
      <div className="text-[10px] capitalize text-muted">
        {p.status}
        {p.parent ? ` · parent ${p.parent}` : ''}
      </div>
    </div>
  )
}
