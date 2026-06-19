import { useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api } from '../lib/api'
import type { GraphNode, RunGraph, RunSummaryDetail } from '../lib/types'
import { compactNum, duration, pct, signedPct, usd } from '../lib/format'
import { prefersReducedMotion, springGrow, easeEnter } from '../lib/motion'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { DiffFileView } from './DiffRows'

const SIZE = 560
const CX = SIZE / 2
const CY = SIZE / 2
const OUTER_R = 210
const INNER_R = 116
const ZOOM_MIN = 0.5
const ZOOM_MAX = 3

const FILL: Record<GraphNode['status'], string> = {
  seed: 'var(--seed)',
  accepted: 'var(--accepted)',
  rejected: 'var(--rejected)',
  failed: 'var(--muted)',
}

interface Placed {
  node: GraphNode
  x: number
  y: number
  r: number
  isChamp: boolean
}

/** Radial iteration ring: the seed sits at the centre, every candidate is placed
 * around the circle in iteration order, and the running-best champion is pulled onto
 * an inner orbit. Wheel zooms (clamped 0.5–3) and dragging pans a single transform
 * group; clicking a node opens an over-panel with that iteration's eval metrics and
 * its git diff vs parent (reusing the shared diff renderer). */
export function RadialTimeline({
  graph,
  summary,
  runId,
}: {
  graph: RunGraph
  summary: RunSummaryDetail
  runId: string
}) {
  const reduce = prefersReducedMotion()
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [selected, setSelected] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)

  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes])
  const champId = graph.best_id

  const placed = useMemo<Placed[]>(() => {
    const cands = graph.nodes
      .filter((n) => n.id !== 'seed')
      .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
    const N = Math.max(1, cands.length)
    return cands.map((node, i) => {
      const isChamp = node.id === champId
      const ang = (i / N) * 2 * Math.PI - Math.PI / 2
      const r = isChamp ? INNER_R : OUTER_R
      return { node, x: CX + r * Math.cos(ang), y: CY + r * Math.sin(ang), r, isChamp }
    })
  }, [graph.nodes, champId])

  if (graph.nodes.length < 2) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          Not enough candidates yet for the radial ring.
        </div>
      </Card>
    )
  }

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    setZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z * (e.deltaY < 0 ? 1.1 : 1 / 1.1))))
  }
  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return
    setPan({ x: drag.current.px + (e.clientX - drag.current.x), y: drag.current.py + (e.clientY - drag.current.y) })
  }
  const onPointerUp = () => {
    drag.current = null
  }

  const sel = selected ? byId.get(selected) : undefined

  return (
    <Card className="relative overflow-hidden p-0">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2 text-xs text-muted">
        <div className="flex items-center gap-3">
          <Legend color="var(--accepted)" label="accepted" />
          <Legend color="var(--rejected)" label="rejected" />
          <Legend color="var(--muted)" label="failed" />
          <Legend color="var(--accent)" label="champion (inner orbit)" />
        </div>
        <div className="flex items-center gap-2">
          <span className="tnum">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            onClick={() => {
              setZoom(1)
              setPan({ x: 0, y: 0 })
            }}
            className="rounded border border-border bg-surface-2 px-2 py-0.5 hover:bg-surface"
          >
            reset
          </button>
        </div>
      </div>

      <div
        className="cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
        style={{ touchAction: 'none' }}
      >
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width="100%" role="img" aria-label="radial iteration ring">
          <g transform={`translate(${pan.x} ${pan.y}) translate(${CX} ${CY}) scale(${zoom}) translate(${-CX} ${-CY})`}>
            {/* orbit guides */}
            <circle cx={CX} cy={CY} r={OUTER_R} fill="none" stroke="var(--border)" strokeWidth={1} />
            <circle cx={CX} cy={CY} r={INNER_R} fill="none" stroke="var(--border)" strokeDasharray="4 4" strokeWidth={1} />

            {/* spokes from seed */}
            {placed.map((p) => (
              <line key={`spoke-${p.node.id}`} x1={CX} y1={CY} x2={p.x} y2={p.y} stroke="var(--border)" strokeWidth={1} opacity={0.6} />
            ))}

            {/* candidate nodes */}
            {placed.map((p, i) => {
              const isSel = p.node.id === selected
              const dim = p.node.status === 'rejected' || p.node.status === 'failed'
              return (
                <motion.g
                  key={p.node.id}
                  layout={!reduce}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelected((s) => (s === p.node.id ? null : p.node.id))}
                  tabIndex={0}
                  role="button"
                  aria-label={`${p.node.id} ${p.node.status} ${p.node.val != null ? pct(p.node.val) : ''}`}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setSelected(p.node.id)}
                  initial={reduce ? false : { scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: dim ? 0.6 : 1 }}
                  transition={reduce ? { duration: 0 } : { ...springGrow, delay: Math.min(i * 0.025, 0.5) }}
                >
                  {p.isChamp && (
                    <motion.circle
                      cx={p.x}
                      cy={p.y}
                      r={13}
                      fill="none"
                      stroke="var(--accent)"
                      strokeWidth={1.5}
                      animate={reduce ? {} : { r: [13, 17, 13], opacity: [0.7, 0.2, 0.7] }}
                      transition={reduce ? undefined : { duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  )}
                  {isSel && <circle cx={p.x} cy={p.y} r={11} fill="none" stroke="var(--primary)" strokeWidth={2} />}
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={p.isChamp ? 9 : 6}
                    fill={p.isChamp ? 'var(--accent)' : FILL[p.node.status]}
                    stroke="var(--bg)"
                    strokeWidth={1.5}
                  />
                </motion.g>
              )
            })}

            {/* seed at centre */}
            <g>
              <circle cx={CX} cy={CY} r={12} fill="var(--seed)" stroke="var(--bg)" strokeWidth={2} />
              <text x={CX} y={CY + 3} textAnchor="middle" fontSize={9} fontWeight={700} fill="var(--bg)">
                seed
              </text>
            </g>
          </g>
        </svg>
      </div>

      <AnimatePresence>
        {sel && <NodePanel node={sel} parent={sel.parent ? byId.get(sel.parent) : undefined} runId={runId} summary={summary} reduce={reduce} onClose={() => setSelected(null)} />}
      </AnimatePresence>
    </Card>
  )
}

function NodePanel({
  node,
  parent,
  runId,
  summary,
  reduce,
  onClose,
}: {
  node: GraphNode
  parent: GraphNode | undefined
  runId: string
  summary: RunSummaryDetail
  reduce: boolean
  onClose: () => void
}) {
  const { data: diff, isLoading } = useQuery({
    queryKey: ['diff', runId, node.id],
    queryFn: ({ signal }) => api.diff(runId, node.id, signal),
    enabled: node.id !== 'seed',
  })

  const delta = node.val != null && parent?.val != null ? node.val - parent.val : null
  // The matching evaluation row carries the honest runner spend + tasks×trials.
  const evalRow = (summary.evaluations ?? []).find((e) => e.candidate === node.id && e.kind === 'candidate')

  return (
    <motion.div
      className="absolute inset-y-0 right-0 z-10 w-full max-w-md overflow-y-auto border-l border-border bg-surface/95 backdrop-blur-sm"
      initial={reduce ? false : { x: '100%' }}
      animate={{ x: 0 }}
      exit={reduce ? { opacity: 0 } : { x: '100%' }}
      transition={reduce ? { duration: 0 } : easeEnter}
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-mono">{node.id}</span>
          <span className="capitalize text-muted">· {node.status}</span>
        </div>
        <button type="button" onClick={onClose} className="rounded p-1 text-muted hover:bg-surface-2 hover:text-foreground" aria-label="close">
          <X size={15} />
        </button>
      </div>

      <div className="space-y-3 p-4">
        <div className="grid grid-cols-2 gap-2">
          <Metric label="reward" value={pct(node.val)} />
          <Metric
            label="Δ vs parent"
            value={delta != null ? signedPct(delta * 100) : '—'}
            tone={delta == null ? undefined : delta >= 0 ? 'up' : 'down'}
          />
          <Metric label="optimizer $" value={node.opt_cost_usd != null ? usd(node.opt_cost_usd) : '—'} />
          <Metric label="optimizer time" value={duration(node.optimizer_seconds)} />
          <Metric label="optimizer tokens" value={compactNum(node.opt_tokens ?? null)} />
          <Metric label="runner $" value={node.cost_usd ? usd(node.cost_usd) : '—'} />
          <Metric label="runner time" value={duration(node.runner_seconds)} />
          {evalRow && <Metric label="tasks × trials" value={`${evalRow.n_tasks} × ${evalRow.trials}`} />}
        </div>

        <div>
          <div className="mb-2 text-xs uppercase tracking-wide text-muted">
            Diff vs {parent?.id ?? 'parent'}
          </div>
          {node.id === 'seed' ? (
            <p className="py-6 text-center text-sm text-muted">The seed is the baseline — no parent to diff against.</p>
          ) : isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : !diff || diff.files.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">No file changes recorded for this candidate.</p>
          ) : (
            diff.files.map((f) => <DiffFileView key={f.path} file={f} />)
          )}
        </div>
      </div>
    </motion.div>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'up' | 'down' }) {
  return (
    <div className="rounded bg-surface-2 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`tnum mt-0.5 text-sm font-semibold ${tone === 'up' ? 'text-accepted' : tone === 'down' ? 'text-rejected' : ''}`}>
        {value}
      </div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}
