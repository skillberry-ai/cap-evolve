import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { GraphNode, RunObjectives } from '../lib/types'
import { usd } from '../lib/format'
import { Card } from './ui/Card'

/** One chart per series (small multiples, no dual axes). Colour is a dataviz categorical
 *  slot AND each series has its own dash pattern, so none relies on hue alone. */
export const SERIES = [
  { key: 'reward', label: 'Reward', color: 'var(--series-1)', dash: undefined, on: true, fmt: (v: number) => `${(v * 100).toFixed(1)}%`, note: 'higher is better' },
  { key: 'cost_matched_success', label: 'Matched-success cost', color: 'var(--series-2)', dash: '6 3', on: true, fmt: usd, note: 'per success, lower is better' },
  { key: 'cost_overall', label: 'Overall cost', color: 'var(--series-3)', dash: '2 2', on: false, fmt: usd, note: 'shown, not gated' },
  { key: 'latency_s', label: 'Latency', color: 'var(--series-4)', dash: '8 3 2 3', on: false, fmt: (v: number) => `${v.toFixed(1)}s`, note: 'display-only' },
  { key: 'optimizer_cum_usd', label: 'Optimizer spend', color: 'var(--series-5)', dash: '1 3', on: false, fmt: usd, note: 'cumulative' },
] as const
type Key = (typeof SERIES)[number]['key']

export interface SeriesPoint { id: string; iteration: number; champion: boolean; values: Partial<Record<Key, number>> }

/** Candidates in iteration order, with cumulative optimizer spend. Missing values stay
 *  absent (a gap in the line), never 0. */
export function buildSeries(nodes: GraphNode[], obj: RunObjectives): SeriesPoint[] {
  let cum = 0
  return [...nodes]
    .filter((n) => n.iteration != null && obj.candidates[n.id])
    .sort((a, b) => (a.iteration as number) - (b.iteration as number))
    .map((n) => {
      const r = obj.candidates[n.id]
      const values: SeriesPoint['values'] = {}
      for (const k of ['reward', 'cost_matched_success', 'cost_overall', 'latency_s'] as const) {
        const v = r[k]
        if (v != null) values[k] = v
      }
      if (r.optimizer_usd != null) { cum += r.optimizer_usd; values.optimizer_cum_usd = cum }
      return { id: n.id, iteration: n.iteration as number, champion: !!n.best_so_far, values }
    })
}

export function SeriesCharts({ nodes, objectives }: { nodes: GraphNode[]; objectives: RunObjectives }) {
  const [on, setOn] = useState<Set<Key>>(new Set(SERIES.filter((s) => s.on).map((s) => s.key)))
  const points = buildSeries(nodes, objectives)
  if (points.length === 0) return null
  const champs = points.filter((p) => p.champion)
  const toggle = (k: Key) => setOn((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n })
  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="mr-2 text-sm font-medium">Per-candidate series</h3>
        {SERIES.map((s) => (
          <label key={s.key} className="inline-flex items-center gap-1.5 text-xs text-muted">
            <input type="checkbox" checked={on.has(s.key)} onChange={() => toggle(s.key)} aria-label={s.label} />
            <svg width="18" height="6" aria-hidden><line x1="0" y1="3" x2="18" y2="3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} /></svg>
            {s.label}
          </label>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {SERIES.filter((s) => on.has(s.key)).map((s) => {
          const data = points.map((p) => ({ id: p.id, iteration: p.iteration, value: p.values[s.key] ?? null }))
          return (
            <div key={s.key} data-testid={`series-${s.key}`}>
              <div className="mb-1 text-xs text-muted">{s.label} <span className="opacity-70">({s.note})</span></div>
              <div style={{ width: '100%', height: 140 }}>
                <ResponsiveContainer>
                  <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="iteration" stroke="var(--muted)" tick={{ fontSize: 10 }} tickLine={false} />
                    <YAxis stroke="var(--muted)" tick={{ fontSize: 10 }} tickLine={false} width={44} tickFormatter={s.fmt} />
                    <Tooltip formatter={(v) => (typeof v === 'number' ? s.fmt(v) : '—')} labelFormatter={(_, p) => p?.[0]?.payload?.id ?? ''} />
                    {champs.map((c) => (
                      <ReferenceLine key={c.id} x={c.iteration} stroke="var(--muted)" strokeDasharray="1 3" />
                    ))}
                    <Line type="monotone" dataKey="value" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} dot={{ r: 2 }} connectNulls={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })}
      </div>
      <p className="mt-2 text-[11px] text-muted">Dotted vertical lines mark champion changes.</p>
    </Card>
  )
}
