import { useMemo, useState } from 'react'
import type { Activity, RunSummaryDetail, GraphNode, GateDecision } from '../lib/types'

interface RunTimelineProps {
  summary: RunSummaryDetail
  nodes: GraphNode[]
  onActivityClick?: (activityId: string) => void
}

export function RunTimeline({ summary, nodes, onActivityClick }: RunTimelineProps) {
  const [hoveredActivity, setHoveredActivity] = useState<string | null>(null)
  const [selectedActivity, setSelectedActivity] = useState<string | null>(null)

  const { activities, gates, perIteration, evaluations } = useMemo(() => {
    const acts = summary.activities || []
    const gates = summary.gate_decisions || []
    const perIter = summary.per_iteration || []
    const evals = summary.evaluations || []
    return { activities: acts, gates, perIteration: perIter, evaluations: evals }
  }, [summary])

  const { elapsed } = useMemo(() => {
    const elapsed = summary.elapsed_seconds || 0
    return { elapsed }
  }, [summary])

  const iterations = useMemo(() => {
    return [...new Set(activities.filter((a: Activity) => a.iteration).map((a: Activity) => a.iteration!))]
  }, [activities])

  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>()
    nodes.forEach(n => map.set(n.id, n))
    return map
  }, [nodes])

  const gateMap = useMemo(() => {
    const map = new Map<string, GateDecision>()
    gates.forEach(g => map.set(g.candidate, g))
    return map
  }, [gates])

  const perIterMap = useMemo(() => {
    const map = new Map<string, any>()
    perIteration.forEach(p => map.set(p.candidate, p))
    return map
  }, [perIteration])

  // SVG dimensions and layout
  const W = 1200
  const L = 118 // left margin
  const Rr = 22 // right margin
  const T0 = 0
  const T1 = elapsed * 1.01

  const x = (t: number) => L + ((W - L - Rr) * (t - T0)) / (T1 - T0)

  const rows = {
    phase: 8,
    iter: 38,
    optimizer: 74,
    evaluator: 110,
    milestone: 146,
    chart: 186,
  }

  const bh = 24 // bar height
  const chartH = 110
  const H = rows.chart + chartH + 34

  const formatDuration = (seconds: number) => {
    if (!seconds) return '—'
    const s = Math.round(seconds)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`
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

  const handleActivityClick = (activityId: string) => {
    setSelectedActivity(activityId)
    onActivityClick?.(activityId)
  }

  const getActivityTooltip = (a: Activity) => {
    const node = a.candidate ? nodeMap.get(a.candidate) : null

    if (a.type === 'optimize') {
      const p = a.candidate ? perIterMap.get(a.candidate) : null
      return `Iteration ${a.iteration} · optimizer\n${formatDuration(a.end - a.start)} · ${formatUsd(p?.optimizer_usd)} · ${formatTokens(p?.optimizer_tokens)} tok\nproposes ${a.candidate} from ${node?.parent}${a.error ? '\noptimizer exited with an error' : ''}`
    }

    if (a.type === 'evaluate') {
      return `Iteration ${a.iteration} · val evaluation\n${a.candidate}: ${formatPercent(node?.val)} ± ${node?.stderr?.toFixed(3)}\n${formatDuration(a.end - a.start)} · ${formatTokens(node?.tokens)} tok\nfixed ${node?.fixed?.length || 0} · broke ${node?.broke?.length || 0} vs ${node?.parent}`
    }

    if (a.type === 'gate') {
      const g = a.candidate ? gateMap.get(a.candidate) : null
      return `Gate: ${g?.verdict.toUpperCase()} ${a.candidate}\nΔ ${g?.delta?.toFixed(4) || '—'} vs threshold ${g?.threshold || '—'}`
    }

    if (a.type === 'final_eval') {
      const e = evaluations.find(ev => ev.split === a.candidate && ev.candidate === summary.best_id)
      return `${a.candidate} evaluation\n${formatPercent(e?.reward)} · n=${e?.n_tasks || 0} · ${formatDuration(a.end - a.start)} · ${formatTokens(e?.tokens)} tok`
    }

    if (a.type === 'seed') {
      return `Baseline (seed)\nval ${formatPercent(summary.baseline_val)}`
    }

    if (a.type === 'finalize') {
      return `Finalize\nbest ${summary.best_id} · test ${formatPercent(summary.test_reward)}`
    }

    return a.id
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ minWidth: '880px', height: `${H}px` }}
      >
        {/* Grid lines and axis */}
        {Array.from({ length: Math.ceil(T1 / 3600) + 1 }, (_, i) => i * 0.5).map(h => {
          const X = x(h * 3600)
          const major = h % 1 === 0
          if (h * 3600 > T1) return null
          return (
            <g key={h}>
              <line
                x1={X}
                x2={X}
                y1={rows.iter - 4}
                y2={rows.chart + chartH}
                stroke="var(--border)"
                strokeDasharray={major ? undefined : '2 4'}
              />
              {major && x(elapsed) - X > 130 && (
                <text
                  x={X}
                  y={rows.chart + chartH + 18}
                  textAnchor="middle"
                  className="text-[10.5px] fill-[var(--muted)]"
                  fontFamily="var(--font-mono)"
                >
                  {h}h
                </text>
              )}
            </g>
          )
        })}

        {/* End marker */}
        <line
          x1={x(elapsed)}
          x2={x(elapsed)}
          y1={rows.iter - 4}
          y2={rows.chart + chartH}
          stroke="var(--border-strong)"
        />
        <text
          x={x(elapsed)}
          y={rows.chart + chartH + 18}
          textAnchor="end"
          className="text-[10.5px] fill-[var(--muted)]"
          fontFamily="var(--font-mono)"
        >
          end · {formatDuration(elapsed)}
        </text>

        {/* Lane labels */}
        <text x={0} y={rows.phase + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Phase
        </text>
        <text x={0} y={rows.iter + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Iteration
        </text>
        <text x={0} y={rows.optimizer + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Optimizer
        </text>
        <text x={0} y={rows.evaluator + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Evaluator
        </text>
        <text x={0} y={rows.milestone + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Gate
        </text>
        <text x={0} y={rows.chart + 13} className="text-[11px] fill-[var(--muted)] uppercase tracking-wider font-semibold">
          Val score
        </text>

        {/* Phase bands */}
        {summary.algo_extra?.epochs && (
          <g>
            <rect
              x={x(0)}
              y={rows.phase}
              width={x(elapsed) - x(0) - 2}
              height={22}
              rx={5}
              fill="var(--primary)"
              fillOpacity={0.14}
              stroke="var(--primary)"
              strokeOpacity={0.4}
            />
            <text
              x={x(0) + 8}
              y={rows.phase + 15}
              className="text-[11.5px] font-semibold fill-[var(--primary)]"
            >
              Optimize · {summary.algorithm}
            </text>
          </g>
        )}

        {/* Iteration bands */}
        {iterations.map((it: number) => {
          const optAct = activities.find((a: Activity) => a.iteration === it && a.type === 'optimize')
          const evalAct = activities.find((a: Activity) => a.iteration === it && a.type === 'evaluate')
          if (!optAct || !evalAct) return null

          const node = optAct.candidate ? nodeMap.get(optAct.candidate) : null
          const col = node?.status === 'accepted' ? 'var(--accepted)' : 'var(--rejected)'
          const isSelected = selectedActivity === `iter-${it}`
          const isHovered = hoveredActivity === `iter-${it}`

          return (
            <g
              key={it}
              className="cursor-pointer"
              onMouseEnter={() => setHoveredActivity(`iter-${it}`)}
              onMouseLeave={() => setHoveredActivity(null)}
              onClick={() => handleActivityClick(`iter-${it}`)}
            >
              <title>{`Iteration ${it}`}</title>
              <rect
                x={x(optAct.start) + 1}
                y={rows.iter}
                width={x(evalAct.end) - x(optAct.start) - 3}
                height={bh}
                rx={5}
                fill="var(--surface-2)"
                stroke={col}
                strokeOpacity={0.6}
                strokeWidth={isSelected ? 2 : 1}
                style={{ filter: isHovered ? 'brightness(1.15)' : undefined }}
              />
              <text
                x={x(optAct.start) + 8}
                y={rows.iter + 16}
                className="text-[11.5px]"
                pointerEvents="none"
              >
                <tspan className="font-semibold fill-[var(--fg)]">iter {it}</tspan>
                <tspan className="fill-[var(--muted)]"> {node?.status === 'accepted' ? '✓' : '✕'}</tspan>
              </text>
            </g>
          )
        })}

        {/* Activity bars */}
        {activities.map((a: Activity) => {
          if (a.lane !== 'optimizer' && a.lane !== 'evaluator') return null

          const y = rows[a.lane as 'optimizer' | 'evaluator']
          const w = Math.max(3, x(a.end) - x(a.start) - 2)
          const col =
            a.type === 'optimize'
              ? 'var(--primary)'
              : a.type === 'evaluate'
                ? 'var(--indecisive)'
                : 'var(--accent)'

          const node = a.candidate ? nodeMap.get(a.candidate) : null
          const perIter = a.candidate ? perIterMap.get(a.candidate) : null

          let label = ''
          if (a.type === 'optimize') {
            label = formatUsd(perIter?.optimizer_usd)
          } else if (a.type === 'evaluate') {
            label = formatPercent(node?.val)
          }

          const actId = a.type === 'final_eval' ? `finalize/${a.candidate}` : `iter-${a.iteration}/${a.type}`
          const isSelected = selectedActivity === actId
          const isHovered = hoveredActivity === actId

          return (
            <g
              key={a.id}
              className="cursor-pointer"
              onMouseEnter={() => setHoveredActivity(actId)}
              onMouseLeave={() => setHoveredActivity(null)}
              onClick={() => handleActivityClick(actId)}
            >
              <title>{getActivityTooltip(a)}</title>
              <rect
                x={x(a.start) + 1}
                y={y}
                width={w}
                height={bh}
                rx={4}
                fill={col}
                fillOpacity={a.type === 'final_eval' ? 0.85 : 0.8}
                strokeWidth={isSelected ? 2 : 0}
                stroke={isSelected ? 'var(--fg)' : undefined}
                style={{ filter: isHovered ? 'brightness(1.15)' : undefined }}
              />
              {w > 46 && label && (
                <text
                  x={x(a.start) + 7}
                  y={y + 16}
                  className="text-[11px] fill-white"
                  fontFamily="var(--font-mono)"
                  pointerEvents="none"
                >
                  {label}
                </text>
              )}
              {a.error && (
                <text x={x(a.end) - 14} y={y + 16} className="text-[12px] fill-white" pointerEvents="none">
                  ⚠
                </text>
              )}
            </g>
          )
        })}

        {/* Gate milestones */}
        {activities
          .filter((a: Activity) => a.type === 'gate')
          .map((a: Activity) => {
            const my = rows.milestone + 12
            const gate = a.candidate ? gateMap.get(a.candidate) : null
            const col = gate?.verdict === 'accept' ? 'var(--accepted)' : 'var(--rejected)'
            const actId = `iter-${a.iteration}/gate`
            const isSelected = selectedActivity === actId
            const isHovered = hoveredActivity === actId

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
                  style={{ filter: isHovered ? 'brightness(1.15)' : undefined }}
                />
              </g>
            )
          })}

        {/* Val score chart */}
        {(() => {
          const cy0 = rows.chart + 6
          const cy1 = rows.chart + chartH
          const yv = (v: number) => cy1 - (cy1 - cy0) * v

          // Grid lines
          const gridLines = [0, 0.25, 0.5, 0.75, 1].map(v => (
            <g key={v}>
              <line
                x1={L}
                x2={W - Rr}
                y1={yv(v)}
                y2={yv(v)}
                stroke="var(--border)"
                strokeOpacity={0.7}
              />
              <text
                x={L - 6}
                y={yv(v) + 3}
                textAnchor="end"
                className="text-[10.5px] fill-[var(--muted)]"
                fontFamily="var(--font-mono)"
              >
                {(v * 100).toFixed(0)}%
              </text>
            </g>
          ))

          // Best-so-far line
          let best = summary.baseline_val || 0
          let pathData = `M${x(0)} ${yv(best)}`

          const gateActivities = activities.filter((a: Activity) => a.type === 'gate')
          gateActivities.forEach((a: Activity) => {
            const node = a.candidate ? nodeMap.get(a.candidate) : null
            if (node?.best_so_far && node.val && node.val > best) {
              pathData += `H${x(a.start)}V${yv(node.val)}`
              best = node.val
            }
          })

          const lastGate = gateActivities[gateActivities.length - 1]
          if (lastGate) {
            pathData += `H${x(lastGate.end)}`
          }

          // Points
          const points = [
            <circle key="seed" cx={x(0)} cy={yv(summary.baseline_val || 0)} r={5} fill="var(--seed)" />,
            ...gateActivities.map((a: Activity) => {
              const node = a.candidate ? nodeMap.get(a.candidate) : null
              if (!node?.val) return null
              const col = node.status === 'accepted' ? 'var(--accepted)' : 'var(--rejected)'
              return (
                <g key={a.id}>
                  <circle cx={x(a.start)} cy={yv(node.val)} r={5} fill={col} />
                  <text
                    x={x(a.start)}
                    y={yv(node.val) - 9}
                    textAnchor="middle"
                    className="text-[10px] fill-[var(--muted-strong)]"
                    fontFamily="var(--font-mono)"
                  >
                    {formatPercent(node.val)}
                  </text>
                </g>
              )
            }),
          ]

          return (
            <>
              {gridLines}
              <path d={pathData} fill="none" stroke="var(--accent)" strokeWidth={2} />
              {points}
            </>
          )
        })()}
      </svg>

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
      </div>
    </div>
  )
}
