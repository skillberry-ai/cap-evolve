import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { Activity, RunSummaryDetail, GraphNode, GateDecision, PerIterationCost, RunGraph } from '../lib/types'
import { layoutLineage } from '../lib/lineage'
import { FILL } from './LineageTree'

interface RunTimelineProps {
  summary: RunSummaryDetail
  nodes: GraphNode[]
  /** Full candidate graph (nodes + root/best_id), used to lay out the branch/merge
   *  lane below the chart — reuses #669's lineage layout rather than reimplementing
   *  DAG layout here. Omitted in a few older tests; the lane is simply skipped then. */
  graph?: RunGraph
  onActivityClick?: (activityId: string) => void
}

const formatDuration = (seconds: number) => {
  if (!seconds) return '—'
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`
}

const formatClock = (t: number) => {
  const h = Math.floor(t / 3600)
  const m = Math.round((t % 3600) / 60)
  return m ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`
}

const formatPercent = (v: number | null | undefined, d = 1) => {
  return v == null ? '—' : `${(v * 100).toFixed(d)}%`
}

const formatUsd = (v: number | null | undefined) => {
  return v == null ? '—' : `$${v.toFixed(2)}`
}

const formatTokens = (v: number | null | undefined) => {
  if (v == null) return '—'
  return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}K` : String(v)
}

// Older payloads (and parallel batches before the backend clamp) can carry end < start.
const span = (a: Activity) => [Math.min(a.start, a.end), Math.max(a.start, a.end)] as const

interface NarrowLabel { cx: number; text: string; base: string; usd?: number; n: number; row: number }

/** Place labels for bars too narrow to hold them in up to two rows under the lane.
 *  A label that fits no row is merged into the previous one (costs are summed:
 *  "Σ$4.12 ×3") — never silently dropped. */
function placeNarrow(items: { cx: number; text: string; usd?: number }[]): NarrowLabel[] {
  const CH = 5.6 // ~px per char at 9px mono
  const ends = [-Infinity, -Infinity]
  const out: NarrowLabel[] = []
  for (const it of [...items].sort((a, b) => a.cx - b.cx)) {
    const half = (it.text.length * CH) / 2
    const row = ends.findIndex(e => it.cx - half >= e + 4)
    if (row >= 0 || !out.length) {
      const r = Math.max(row, 0)
      out.push({ ...it, base: it.text, n: 1, row: r })
      ends[r] = it.cx + half
      continue
    }
    const g = out[out.length - 1]
    g.n += 1
    g.usd = g.usd != null && it.usd != null ? g.usd + it.usd : undefined
    g.text = g.usd != null ? `Σ${formatUsd(g.usd)} ×${g.n}` : `${g.base} +${g.n - 1}`
    ends[g.row] = Math.max(ends[g.row], g.cx + (g.text.length * CH) / 2)
  }
  return out
}

export function RunTimeline({ summary, nodes, graph, onActivityClick }: RunTimelineProps) {
  const [hoveredActivity, setHoveredActivity] = useState<string | null>(null)
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null)

  const { activities, gates, perIteration, evaluations } = useMemo(() => ({
    activities: summary.activities || [],
    gates: summary.gate_decisions || [],
    perIteration: summary.per_iteration || [],
    evaluations: summary.evaluations || [],
  }), [summary])
  const elapsed = summary.elapsed_seconds || 0

  // Every activity carrying an iteration, grouped — an iteration renders a band as
  // long as ANY of its activities exists (no 1:1 optimize/evaluate requirement).
  const iterGroups = useMemo(() => {
    const m = new Map<number, Activity[]>()
    for (const a of activities) {
      if (!a.iteration) continue
      if (!m.has(a.iteration)) m.set(a.iteration, [])
      m.get(a.iteration)!.push(a)
    }
    return [...m.entries()]
  }, [activities])

  const nodeMap = useMemo(() => new Map<string, GraphNode>(nodes.map(n => [n.id, n])), [nodes])
  const gateMap = useMemo(() => new Map<string, GateDecision>(gates.map(g => [g.candidate, g])), [gates])
  const perIterMap = useMemo(() => new Map<string, PerIterationCost>(perIteration.map(p => [p.candidate, p])), [perIteration])

  // --- branch/merge graph lane --------------------------------------------
  // Reuses #669's lineage layout for branch-lane assignment and merge_of edges;
  // this view just projects it onto the same time axis as the activity bars above,
  // instead of the Lineage tab's depth-column x-axis.
  const branchLayout = useMemo(() => (graph ? layoutLineage(graph) : null), [graph])
  // Each candidate's x position: the time it was decided (gate), else evaluated,
  // else when its optimizer call started. Falls back to run start (0) when a node
  // (e.g. seed on older payloads) has no matching activity at all.
  const candTime = useMemo(() => {
    const priority: Record<Activity['type'], number> = { gate: 4, evaluate: 3, final_eval: 3, grow: 2, optimize: 1, seed: 0, finalize: 0 }
    const best = new Map<string, { t: number; p: number }>()
    for (const a of activities) {
      if (!a.candidate) continue
      const p = priority[a.type]
      const cur = best.get(a.candidate)
      if (!cur || p > cur.p) best.set(a.candidate, { t: span(a)[0], p })
    }
    return new Map([...best].map(([k, v]) => [k, v.t]))
  }, [activities])

  // --- zoom / pan --------------------------------------------------------
  const scrollRef = useRef<HTMLDivElement>(null)
  const [baseW, setBaseW] = useState(1082) // visible plot width at zoom 1 (measured)
  const [zoom, setZoom] = useState(1)
  // Zoom range grows with activity count: a dense run can be opened up to roughly
  // ~4 activities per screen width.
  const maxZoom = Math.max(4, Math.ceil(activities.length / 4))
  const anchor = useRef<{ frac: number; mx: number } | null>(null)

  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const measure = () => { if (el.clientWidth) setBaseW(Math.max(el.clientWidth, 600)) }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  const zoomTo = (z: number, mx?: number) => {
    const nz = Math.min(maxZoom, Math.max(1, z))
    const el = scrollRef.current
    if (el) {
      const m = mx ?? el.clientWidth / 2
      anchor.current = { frac: (el.scrollLeft + m) / (baseW * zoom), mx: m }
    }
    setZoom(nz)
  }

  // Keep the time under the cursor (or the view centre) fixed while zooming.
  useLayoutEffect(() => {
    const el = scrollRef.current
    const a = anchor.current
    if (el && a) el.scrollLeft = a.frac * baseW * zoom - a.mx
    anchor.current = null
  }, [zoom, baseW])

  // Ctrl/⌘ + wheel (and trackpad pinch, which arrives as ctrl+wheel) zooms. Needs a
  // non-passive native listener so preventDefault stops the page zoom.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      zoomTo(zoom * Math.exp(-e.deltaY * 0.002), e.clientX - el.getBoundingClientRect().left)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  const drag = useRef<{ x: number; left: number } | null>(null)

  // --- layout ------------------------------------------------------------
  const L = 118 // fixed left gutter (lane labels + y axis); does not scroll
  const PAD = 10
  const Rr = 22
  const W = baseW * zoom
  const T1 = Math.max(elapsed * 1.01, 1)
  const x = (t: number) => PAD + ((W - PAD - Rr) * t) / T1

  // Branch/merge lane: one row per lineage lane (0 when no `graph` was passed), each
  // 20px tall, inserted between the gate diamonds and the val-score chart.
  const branchRows = branchLayout?.rows ?? 0
  const branchLaneH = 20
  const branchAreaH = branchRows > 0 ? 10 + branchRows * branchLaneH : 0

  const rows = {
    phase: 8,
    iter: 38,
    optimizer: 74, // + two narrow-label rows below
    evaluator: 128, // + two narrow-label rows below
    milestone: 182,
    branches: 222,
    chart: 222 + branchAreaH,
  }
  const bh = 24 // bar height
  const chartH = 110
  const H = rows.chart + chartH + 34

  const pxPerSec = (W - PAD - Rr) / T1
  const tickStep = [60, 300, 600, 900, 1800, 3600, 7200, 14400].find(s => s * pxPerSec >= 70) ?? 28800

  const handleActivityClick = (activityId: string) => {
    setSelectedActivity(activityId)
    onActivityClick?.(activityId)
  }

  const getActivityTooltip = (a: Activity) => {
    const node = a.candidate ? nodeMap.get(a.candidate) : null
    const [s, e] = span(a)

    if (a.type === 'optimize') {
      const p = a.candidate ? perIterMap.get(a.candidate) : null
      return `Iteration ${a.iteration} · optimizer\n${formatDuration(e - s)} · ${formatUsd(p?.optimizer_usd)} · ${formatTokens(p?.optimizer_tokens)} tok\nproposes ${a.candidate} from ${node?.parent}${a.error ? '\noptimizer exited with an error' : ''}`
    }

    if (a.type === 'evaluate') {
      return `Iteration ${a.iteration} · val evaluation\n${a.candidate}: ${formatPercent(node?.val)} ± ${node?.stderr?.toFixed(3)}\n${formatDuration(e - s)} · ${formatTokens(node?.tokens)} tok\nfixed ${node?.fixed?.length || 0} · broke ${node?.broke?.length || 0} vs ${node?.parent}`
    }

    if (a.type === 'grow') {
      return `Iteration ${a.iteration} · growth round ${a.growth_round}\n${a.candidate}: extra val trials ${formatPercent(a.reward)}\n${formatDuration(e - s)}`
    }

    if (a.type === 'gate') {
      const g = a.candidate ? gateMap.get(a.candidate) : null
      return `Gate: ${g?.verdict.toUpperCase()} ${a.candidate}\nΔ ${g?.delta?.toFixed(4) || '—'} vs threshold ${g?.threshold || '—'}`
    }

    if (a.type === 'final_eval') {
      const ev = evaluations.find(v => v.split === a.split && v.candidate === summary.best_id)
      return `${a.split ?? a.candidate} evaluation\n${formatPercent(ev?.reward)} · n=${ev?.n_tasks || 0} · ${formatDuration(e - s)} · ${formatTokens(ev?.tokens)} tok`
    }

    if (a.type === 'seed') {
      return `Baseline (seed)\nval ${formatPercent(summary.baseline_val)}`
    }

    if (a.type === 'finalize') {
      return `Finalize\nbest ${summary.best_id} · test ${formatPercent(summary.test_reward)}`
    }

    return a.id
  }

  const actIdOf = (a: Activity) =>
    a.type === 'final_eval' ? `finalize/${a.candidate}`
      : a.type === 'grow' ? `iter-${a.iteration}/grow${a.growth_round}`
        : `iter-${a.iteration}/${a.type}`

  const barActs = activities.filter(a => a.lane === 'optimizer' || a.lane === 'evaluator')

  const labelOf = (a: Activity) => {
    if (a.type === 'optimize') {
      const usd = a.candidate ? perIterMap.get(a.candidate)?.optimizer_usd : undefined
      return { text: formatUsd(usd), usd: usd ?? undefined }
    }
    if (a.type === 'evaluate') return { text: formatPercent(a.candidate ? nodeMap.get(a.candidate)?.val : null) }
    if (a.type === 'grow') return { text: `g${a.growth_round} ${formatPercent(a.reward)}` }
    return null
  }
  const barW = (a: Activity) => { const [s, e] = span(a); return Math.max(3, x(e) - x(s) - 2) }
  const fitsInside = (a: Activity, text: string) => barW(a) > text.length * 6.6 + 10

  const narrow = (lane: 'optimizer' | 'evaluator') =>
    placeNarrow(barActs.flatMap(a => {
      const l = a.lane === lane ? labelOf(a) : null
      if (!l || fitsInside(a, l.text)) return []
      return [{ cx: x(span(a)[0]) + 1 + barW(a) / 2, ...l }]
    }))

  const laneLabel = (y: number, text: string) => (
    <text x={0} y={y + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
      {text}
    </text>
  )

  const cy0 = rows.chart + 6
  const cy1 = rows.chart + chartH
  const yv = (v: number) => cy1 - (cy1 - cy0) * v
  const gateActivities = activities.filter(a => a.type === 'gate')

  const btn = 'px-2 py-0.5 rounded border border-[var(--border)] text-xs hover:bg-[var(--surface-2)] disabled:opacity-40'

  return (
    <div className="w-full">
      {/* Zoom controls */}
      <div className="flex items-center gap-2 text-xs text-[var(--muted)] mb-2">
        <button type="button" className={btn} aria-label="Zoom out" disabled={zoom <= 1} onClick={() => zoomTo(zoom / 1.5)}>−</button>
        <input
          type="range"
          aria-label="Zoom"
          min={1}
          max={maxZoom}
          step={0.1}
          value={zoom}
          onChange={e => zoomTo(Number(e.target.value))}
          className="w-40"
        />
        <button type="button" className={btn} aria-label="Zoom in" disabled={zoom >= maxZoom} onClick={() => zoomTo(zoom * 1.5)}>+</button>
        <button type="button" className={btn} aria-label="Fit whole run" disabled={zoom === 1} onClick={() => zoomTo(1)}>Fit</button>
        <span className="font-mono">{zoom.toFixed(1)}×</span>
        <span>· Ctrl/⌘ + scroll to zoom · drag to pan</span>
      </div>

      <div className="flex">
        {/* Fixed gutter: lane labels and val axis stay visible while panning */}
        <svg width={L} height={H} className="shrink-0">
          {laneLabel(rows.phase, 'Phase')}
          {laneLabel(rows.iter, 'Iteration')}
          {laneLabel(rows.optimizer, 'Optimizer')}
          {laneLabel(rows.evaluator, 'Evaluator')}
          {laneLabel(rows.milestone, 'Gate')}
          {branchRows > 0 && laneLabel(rows.branches, 'Branches')}
          {laneLabel(rows.chart, 'Val score')}
          {[0, 0.25, 0.5, 0.75, 1].map(v => (
            <text key={v} x={L - 6} y={yv(v) + 3} textAnchor="end" className="text-[10.5px] fill-[var(--muted)]" fontFamily="var(--font-mono)">
              {(v * 100).toFixed(0)}%
            </text>
          ))}
        </svg>

        <div
          ref={scrollRef}
          data-testid="timeline-scroll"
          className={`flex-1 min-w-0 overflow-x-auto ${zoom > 1 ? 'cursor-grab' : ''}`}
          onPointerDown={e => { if (e.button === 0 && scrollRef.current) drag.current = { x: e.clientX, left: scrollRef.current.scrollLeft } }}
          onPointerMove={e => { if (drag.current && scrollRef.current) scrollRef.current.scrollLeft = drag.current.left - (e.clientX - drag.current.x) }}
          onPointerUp={() => { drag.current = null }}
          onPointerLeave={() => { drag.current = null }}
        >
          {/* ponytail: every element is drawn (no windowing); fine to a few hundred activities, cull to the visible scroll range if runs get far larger. */}
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
            {/* Grid lines and axis */}
            {Array.from({ length: Math.floor(T1 / tickStep) + 1 }, (_, i) => i * tickStep).map(t => {
              const X = x(t)
              const major = t % 3600 === 0
              return (
                <g key={t}>
                  <line x1={X} x2={X} y1={rows.iter - 4} y2={rows.chart + chartH} stroke="var(--border)" strokeDasharray={major ? undefined : '2 4'} />
                  {x(elapsed) - X > 90 && (
                    <text x={X} y={rows.chart + chartH + 18} textAnchor="middle" className="text-[10.5px] fill-[var(--muted)]" fontFamily="var(--font-mono)">
                      {formatClock(t)}
                    </text>
                  )}
                </g>
              )
            })}

            {/* End marker */}
            <line x1={x(elapsed)} x2={x(elapsed)} y1={rows.iter - 4} y2={rows.chart + chartH} stroke="var(--border-strong)" />
            <text x={x(elapsed)} y={rows.chart + chartH + 18} textAnchor="end" className="text-[10.5px] fill-[var(--muted)]" fontFamily="var(--font-mono)">
              end · {formatDuration(elapsed)}
            </text>

            {/* Phase bands */}
            {summary.algo_extra?.epochs && (
              <g>
                <rect x={x(0)} y={rows.phase} width={Math.max(0, x(elapsed) - x(0) - 2)} height={22} rx={5} fill="var(--primary)" fillOpacity={0.14} stroke="var(--primary)" strokeOpacity={0.4} />
                <text x={x(0) + 8} y={rows.phase + 15} className="text-[11.5px] font-semibold fill-[var(--primary)]">
                  Optimize · {summary.algorithm}
                </text>
              </g>
            )}

            {/* Iteration bands: span every non-gate activity of the iteration (falls back
                to the gate alone), with growth rounds as ticks along the bottom. */}
            {iterGroups.map(([it, acts]) => {
              const work = acts.filter(a => a.type !== 'gate')
              const spanActs = work.length ? work : acts
              const s = Math.min(...spanActs.map(a => span(a)[0]))
              const e = Math.max(...spanActs.map(a => span(a)[1]))
              const grows = acts.filter(a => a.type === 'grow')
              const cand = (acts.find(a => a.type === 'optimize' || a.type === 'evaluate') ?? acts[0]).candidate
              const node = cand ? nodeMap.get(cand) : null
              const col = node?.status === 'accepted' ? 'var(--accepted)' : 'var(--rejected)'
              const id = `iter-${it}`
              const w = Math.max(8, x(e) - x(s) - 3)
              const mark = node?.status === 'accepted' ? '✓' : '✕'

              return (
                <g
                  key={it}
                  data-testid={`iter-band-${it}`}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredActivity(id)}
                  onMouseLeave={() => setHoveredActivity(null)}
                  onClick={() => handleActivityClick(id)}
                >
                  <title>{`Iteration ${it} · ${cand ?? '—'} · ${node?.status ?? 'unknown'}${grows.length ? ` · ${grows.length} growth round${grows.length > 1 ? 's' : ''}` : ''}`}</title>
                  <rect
                    x={x(s) + 1}
                    y={rows.iter}
                    width={w}
                    height={bh}
                    rx={5}
                    fill="var(--surface-2)"
                    fillOpacity={0.85}
                    stroke={col}
                    strokeOpacity={0.6}
                    strokeWidth={selectedActivity === id ? 2 : 1}
                    style={{ filter: hoveredActivity === id ? 'brightness(1.15)' : undefined }}
                  />
                  {grows.map(g => (
                    <rect key={g.id} x={x(span(g)[0]) + 1} y={rows.iter + bh - 5} width={Math.max(3, x(span(g)[1]) - x(span(g)[0]) - 2)} height={3} rx={1.5} fill="var(--indecisive)" />
                  ))}
                  <text x={x(s) + 8} y={rows.iter + 16} className="text-[11.5px]" pointerEvents="none">
                    {w > 70 ? (
                      <>
                        <tspan className="font-semibold fill-[var(--fg)]">iter {it}</tspan>
                        <tspan className="fill-[var(--muted)]"> {mark}{grows.length ? ` +${grows.length} grow` : ''}</tspan>
                      </>
                    ) : (
                      <tspan className="font-semibold fill-[var(--fg)]">{it}</tspan>
                    )}
                  </text>
                </g>
              )
            })}

            {/* Activity bars */}
            {barActs.map(a => {
              const y = rows[a.lane as 'optimizer' | 'evaluator']
              const [s] = span(a)
              const w = barW(a)
              const col = a.type === 'optimize' ? 'var(--primary)' : a.type === 'evaluate' || a.type === 'grow' ? 'var(--indecisive)' : 'var(--accent)'
              const l = labelOf(a)
              const actId = actIdOf(a)
              const isSelected = selectedActivity === actId

              return (
                <g
                  key={a.id}
                  data-testid={`bar-${a.id}`}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredActivity(actId)}
                  onMouseLeave={() => setHoveredActivity(null)}
                  onClick={() => handleActivityClick(actId)}
                >
                  <title>{getActivityTooltip(a)}</title>
                  <rect
                    x={x(s) + 1}
                    y={y}
                    width={w}
                    height={bh}
                    rx={4}
                    fill={col}
                    fillOpacity={a.type === 'grow' ? 0.45 : a.type === 'final_eval' ? 0.85 : 0.8}
                    strokeWidth={isSelected ? 2 : a.type === 'grow' ? 1 : 0}
                    stroke={isSelected ? 'var(--fg)' : a.type === 'grow' ? 'var(--indecisive)' : undefined}
                    strokeDasharray={a.type === 'grow' && !isSelected ? '3 2' : undefined}
                    style={{ filter: hoveredActivity === actId ? 'brightness(1.15)' : undefined }}
                  />
                  {l && fitsInside(a, l.text) && (
                    <text x={x(s) + 7} y={y + 16} className="text-[11px] fill-white" fontFamily="var(--font-mono)" pointerEvents="none">
                      {l.text}
                    </text>
                  )}
                  {a.error && (
                    <text x={x(s) + w - 12} y={y + 16} className="text-[12px] fill-white" pointerEvents="none">⚠</text>
                  )}
                </g>
              )
            })}

            {/* Labels for bars too narrow to hold them: under the lane, merged if crowded */}
            {(['optimizer', 'evaluator'] as const).flatMap(lane =>
              narrow(lane).map(nl => (
                <text
                  key={`${lane}-${nl.cx}`}
                  data-testid={`narrow-label-${lane}`}
                  x={nl.cx}
                  y={rows[lane] + bh + 9 + nl.row * 10}
                  textAnchor="middle"
                  className="text-[9px] fill-[var(--muted-strong)]"
                  fontFamily="var(--font-mono)"
                  pointerEvents="none"
                >
                  {nl.text}
                </text>
              )),
            )}

            {/* Gate milestones */}
            {gateActivities.map(a => {
              const my = rows.milestone + 12
              const gate = a.candidate ? gateMap.get(a.candidate) : null
              const col = gate?.verdict === 'accept' ? 'var(--accepted)' : 'var(--rejected)'
              const actId = `iter-${a.iteration}/gate`
              const isSelected = selectedActivity === actId
              return (
                <g
                  key={a.id}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredActivity(actId)}
                  onMouseLeave={() => setHoveredActivity(null)}
                  onClick={() => handleActivityClick(actId)}
                >
                  <title>{getActivityTooltip(a)}</title>
                  <path
                    d={`M${x(a.start)} ${my - 8}L${x(a.start) + 8} ${my}L${x(a.start)} ${my + 8}L${x(a.start) - 8} ${my}Z`}
                    fill={col}
                    strokeWidth={isSelected ? 2 : 0}
                    stroke={isSelected ? 'var(--fg)' : undefined}
                    style={{ filter: hoveredActivity === actId ? 'brightness(1.15)' : undefined }}
                  />
                </g>
              )
            })}

            {/* Branch/merge graph: same node/edge visual language as the Lineage tab
                (#669 — accent spine, dashed muted merge_of edges), projected onto this
                lane's own time axis instead of depth columns, so WHEN a branch/merge
                happened lines up with the activity bars above it. */}
            {branchLayout && branchRows > 0 && (() => {
              const pos = new Map(branchLayout.nodes.map(n => [n.id, n]))
              const nx = (id: string) => x(candTime.get(id) ?? 0)
              const ny = (row: number) => rows.branches + 10 + row * branchLaneH + branchLaneH / 2
              return (
                <g>
                  {branchLayout.edges.map(e => {
                    const a = pos.get(e.from)
                    const b = pos.get(e.to)
                    if (!a || !b) return null
                    const x1 = nx(a.id); const y1 = ny(a.row)
                    const x2 = nx(b.id); const y2 = ny(b.row)
                    return (
                      <path
                        key={`${e.from}-${e.to}-${e.merge ? 'merge' : 'derive'}`}
                        d={`M${x1} ${y1}H${(x1 + x2) / 2}V${y2}H${x2}`}
                        fill="none"
                        stroke={e.onSpine ? 'var(--accent)' : e.merge ? 'var(--muted)' : 'var(--border)'}
                        strokeWidth={e.onSpine ? 2 : 1.2}
                        strokeDasharray={e.merge ? '4 3' : undefined}
                      />
                    )
                  })}
                  {branchLayout.nodes.map(n => {
                    const cx = nx(n.id); const cy = ny(n.row)
                    const actId = n.id === 'seed' ? 'seed' : `iter-${nodeMap.get(n.id)?.iteration ?? ''}`
                    return (
                      <g
                        key={n.id}
                        className="cursor-pointer"
                        onMouseEnter={() => setHoveredActivity(actId)}
                        onMouseLeave={() => setHoveredActivity(null)}
                        onClick={() => handleActivityClick(actId)}
                      >
                        <title>{`${n.id} · ${n.status}${n.val != null ? ` · ${formatPercent(n.val)}` : ''}${n.mergeOf?.length ? `\nmerges ${[n.parent, ...n.mergeOf].filter(Boolean).join(' + ')}` : ''}`}</title>
                        {n.id === graph?.best_id && <circle cx={cx} cy={cy} r={8} fill="none" stroke="var(--accent)" strokeWidth={1.5} opacity={0.6} />}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={5}
                          fill={n.id === graph?.best_id ? 'var(--accent)' : FILL[n.status]}
                          stroke="var(--bg)"
                          strokeWidth={1.5}
                          style={{ filter: hoveredActivity === actId ? 'brightness(1.2)' : undefined }}
                        />
                      </g>
                    )
                  })}
                </g>
              )
            })()}

            {/* Val score chart */}
            {(() => {
              let best = summary.baseline_val || 0
              let pathData = `M${x(0)} ${yv(best)}`
              gateActivities.forEach(a => {
                const node = a.candidate ? nodeMap.get(a.candidate) : null
                if (node?.best_so_far && node.val && node.val > best) {
                  pathData += `H${x(a.start)}V${yv(node.val)}`
                  best = node.val
                }
              })
              const lastGate = gateActivities[gateActivities.length - 1]
              if (lastGate) pathData += `H${x(lastGate.end)}`

              return (
                <>
                  {[0, 0.25, 0.5, 0.75, 1].map(v => (
                    <line key={v} x1={0} x2={W - Rr} y1={yv(v)} y2={yv(v)} stroke="var(--border)" strokeOpacity={0.7} />
                  ))}
                  <path d={pathData} fill="none" stroke="var(--accent)" strokeWidth={2} />
                  <circle cx={x(0)} cy={yv(summary.baseline_val || 0)} r={5} fill="var(--seed)" />
                  {gateActivities.map(a => {
                    const node = a.candidate ? nodeMap.get(a.candidate) : null
                    if (!node?.val) return null
                    const col = node.status === 'accepted' ? 'var(--accepted)' : 'var(--rejected)'
                    return (
                      <g key={a.id}>
                        <circle cx={x(a.start)} cy={yv(node.val)} r={5} fill={col} />
                        <text x={x(a.start)} y={yv(node.val) - 9} textAnchor="middle" className="text-[10px] fill-[var(--muted-strong)]" fontFamily="var(--font-mono)">
                          {formatPercent(node.val)}
                        </text>
                      </g>
                    )
                  })}
                </>
              )
            })()}
          </svg>
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 flex-wrap text-xs text-[var(--muted)] mt-2">
        <span className="inline-flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-[var(--primary)]" />
          optimizer call
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-[var(--indecisive)]" />
          evaluation on val
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="w-3 h-3 rounded border border-dashed border-[var(--indecisive)]" style={{ background: 'color-mix(in srgb, var(--indecisive) 45%, transparent)' }} />
          growth round (extra val trials)
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-[var(--accent)]" />
          final evaluation
        </span>
        <span className="inline-flex items-center gap-2">
          <svg width="12" height="12">
            <path d="M6 0L12 6L6 12L0 6Z" fill="var(--accepted)" />
          </svg>
          gate accept
        </span>
        <span className="inline-flex items-center gap-2">
          <svg width="12" height="12">
            <path d="M6 0L12 6L6 12L0 6Z" fill="var(--rejected)" />
          </svg>
          gate reject
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-[var(--accent)]" />
          best-so-far val
        </span>
        {branchRows > 0 && (
          <span className="inline-flex items-center gap-2">
            <svg width="12" height="4" aria-hidden>
              <line x1={0} y1={2} x2={12} y2={2} stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="3 2" />
            </svg>
            merge edge (branches lane)
          </span>
        )}
      </div>
    </div>
  )
}
