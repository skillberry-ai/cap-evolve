import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { GraphNode } from '../lib/types'
import { cumulativeBest, type CurvePoint } from '../lib/bestCurve'
import { pct } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'
import { Card } from './ui/Card'

const COLOR: Record<GraphNode['status'], string> = {
  seed: 'var(--seed)',
  accepted: 'var(--accepted)',
  rejected: 'var(--rejected)',
  // An indecisive point is plotted, but in its own hue and hollow: the gate refused to
  // judge it, so it never sets the running-best stair.
  indecisive: 'var(--indecisive)',
  failed: 'var(--failed)',
}

/** Per-iteration val scatter under the amber cumulative-best stair. */
export function BestCurveChart({ nodes }: { nodes: GraphNode[] }) {
  const data = cumulativeBest(nodes)
  const reduce = prefersReducedMotion()

  if (data.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No scored candidates yet — the fitness curve appears as evaluation begins.
        </div>
      </Card>
    )
  }

  const championBest = Math.max(...data.map((d) => d.best))
  const anyStderr = data.some((d) => d.stderr != null)

  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">
          Val score per candidate, with the cumulative best
        </h3>
        <span className="tnum text-xs text-muted">
          best <span className="text-accent">{pct(championBest)}</span>
          {anyStderr
            ? ' · hover a point (or open the data table) for ± SE'
            : ' · no stderr recorded for this run'}
        </span>
      </div>
      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="iteration"
              stroke="var(--muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              label={{ value: 'iteration', position: 'insideBottom', offset: -2, fontSize: 10, fill: 'var(--muted)' }}
            />
            <YAxis
              domain={[0, 1]}
              stroke="var(--muted)"
              tick={{ fontSize: 11 }}
              tickLine={false}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
            />
            <Tooltip content={<CurveTooltip />} />
            <Line
              type="stepAfter"
              dataKey="best"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={!reduce}
              animationDuration={600}
            />
            <Scatter
              dataKey="val"
              isAnimationActive={!reduce}
              shape={(props: unknown) => <CandidateDot {...(props as DotProps)} />}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Accessible table alternative */}
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-muted">View data table</summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-muted">
            <tr>
              <th className="py-1 pr-3 font-medium">iter</th>
              <th className="py-1 pr-3 font-medium">candidate</th>
              <th className="py-1 pr-3 font-medium">val ± SE</th>
              <th className="py-1 font-medium">best</th>
            </tr>
          </thead>
          <tbody className="tnum">
            {data.map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="py-1 pr-3">{d.iteration}</td>
                <td className="py-1 pr-3">{d.id}</td>
                <td className="py-1 pr-3">
                  {pct(d.val)}
                  {d.stderr != null ? ` ± ${d.stderr.toFixed(3)}` : ''}
                </td>
                <td className="py-1">{pct(d.best)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Card>
  )
}

interface DotProps {
  cx?: number
  cy?: number
  payload?: CurvePoint
}

function CandidateDot({ cx, cy, payload }: DotProps) {
  if (cx == null || cy == null || !payload) return null
  return (
    <g>
      {payload.isChampion ? (
        <Star cx={cx} cy={cy} />
      ) : payload.status === 'indecisive' ? (
        // hollow: the gate refused to judge, so there is no verdict to fill in
        <circle cx={cx} cy={cy} r={4.5} fill="var(--bg)" stroke={COLOR.indecisive} strokeWidth={2} />
      ) : (
        <circle cx={cx} cy={cy} r={4} fill={COLOR[payload.status]} stroke="var(--bg)" strokeWidth={1} />
      )}
    </g>
  )
}

function Star({ cx, cy }: { cx: number; cy: number }) {
  const pts = []
  for (let i = 0; i < 10; i++) {
    const r = i % 2 === 0 ? 7 : 3
    const a = (Math.PI / 5) * i - Math.PI / 2
    pts.push(`${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`)
  }
  return <polygon points={pts.join(' ')} fill="var(--accent)" stroke="var(--bg)" strokeWidth={0.5} />
}

function CurveTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: CurvePoint }> }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs shadow-lg">
      <div className="font-medium">{p.id}</div>
      <div className="tnum text-muted">
        val <span className="text-foreground">{pct(p.val)}</span>
        {p.stderr != null && <span> ± {p.stderr.toFixed(3)}</span>} · best{' '}
        <span className="text-accent">{pct(p.best)}</span>
      </div>
      <div className="text-[10px] capitalize text-muted">{p.status}{p.isRecord ? ' · new record' : ''}</div>
    </div>
  )
}
