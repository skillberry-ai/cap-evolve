import { useState } from 'react'
import { motion } from 'framer-motion'
import type { RunGraph, GraphNode } from '../lib/types'
import { layoutLineage, type LaidNode } from '../lib/lineage'
import { pct } from '../lib/format'
import { prefersReducedMotion, springGrow } from '../lib/motion'
import { Card } from './ui/Card'

const COL_W = 120
const ROW_H = 76
const PAD = 32
const R = 18

const FILL: Record<GraphNode['status'], string> = {
  seed: 'var(--seed)',
  accepted: 'var(--accepted)',
  rejected: 'var(--rejected)',
  failed: 'var(--muted)',
}

/** Best-path-as-spine lineage: the winning chain reads as a flat amber line
 * across the top; off-spine candidates hang below with L-connectors. */
export function LineageTree({ graph }: { graph: RunGraph }) {
  const layout = layoutLineage(graph)
  const [selected, setSelected] = useState<string | null>(graph.best_id)
  const reduce = prefersReducedMotion()

  if (layout.nodes.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">No candidates yet.</div>
      </Card>
    )
  }

  const pos = new Map(layout.nodes.map((n) => [n.id, n]))
  const x = (col: number) => PAD + col * COL_W + R
  const y = (row: number) => PAD + row * ROW_H + R
  const width = PAD * 2 + layout.cols * COL_W
  const height = PAD * 2 + layout.rows * ROW_H
  const sel = selected ? pos.get(selected) : undefined
  const selParent = sel?.parent ? pos.get(sel.parent) : undefined

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-4 text-xs text-muted">
        <Legend color="var(--accent)" label="best path" />
        <Legend color="var(--accepted)" label="accepted" />
        <Legend color="var(--rejected)" label="rejected" />
        <Legend color="var(--seed)" label="seed" />
      </div>

      <div className="overflow-x-auto">
        <svg width={width} height={height} role="img" aria-label="candidate lineage">
          {/* edges */}
          {layout.edges.map((e) => {
            const a = pos.get(e.from)!
            const b = pos.get(e.to)!
            const x1 = x(a.col)
            const y1 = y(a.row)
            const x2 = x(b.col)
            const y2 = y(b.row)
            const d = `M ${x1} ${y1} H ${(x1 + x2) / 2} V ${y2} H ${x2}`
            return (
              <motion.path
                key={`${e.from}-${e.to}`}
                d={d}
                fill="none"
                stroke={e.onSpine ? 'var(--accent)' : 'var(--border)'}
                strokeWidth={e.onSpine ? 2.5 : 1.5}
                initial={reduce ? false : { pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: reduce ? 0 : 0.4 }}
              />
            )
          })}

          {/* nodes */}
          {layout.nodes.map((n, i) => (
            <LineageNode
              key={n.id}
              node={n}
              cx={x(n.col)}
              cy={y(n.row)}
              isBest={n.id === graph.best_id}
              isSelected={n.id === selected}
              delay={reduce ? 0 : Math.min(i * 0.03, 0.4)}
              reduce={reduce}
              onSelect={() => setSelected(n.id)}
            />
          ))}
        </svg>
      </div>

      {sel && (
        <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-medium">{sel.id}</span>
            <span className="capitalize text-muted">· {sel.status}</span>
            {sel.id === graph.best_id && <span className="text-accent">· champion</span>}
          </div>
          <div className="tnum mt-1 text-muted">
            val <span className="text-foreground">{pct(sel.val)}</span>
            {selParent && (
              <>
                {' '}· parent <span className="text-foreground">{selParent.id}</span>
                {sel.val != null && selParent.val != null && (
                  <>
                    {' '}· Δ{' '}
                    <span className={sel.val - selParent.val >= 0 ? 'text-accepted' : 'text-rejected'}>
                      {pct(sel.val - selParent.val)}
                    </span>
                  </>
                )}
              </>
            )}
          </div>
          {sel.reason && <div className="mt-1 text-xs text-muted">{sel.reason}</div>}
        </div>
      )}
    </Card>
  )
}

function LineageNode({
  node,
  cx,
  cy,
  isBest,
  isSelected,
  delay,
  reduce,
  onSelect,
}: {
  node: LaidNode
  cx: number
  cy: number
  isBest: boolean
  isSelected: boolean
  delay: number
  reduce: boolean
  onSelect: () => void
}) {
  const dim = node.status === 'rejected' || node.status === 'failed'
  return (
    <motion.g
      style={{ cursor: 'pointer', transformOrigin: `${cx}px ${cy}px` }}
      onClick={onSelect}
      tabIndex={0}
      role="button"
      aria-label={`${node.id} ${node.status} ${node.val != null ? pct(node.val) : ''}`}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect()}
      initial={reduce ? false : { scale: 0.4, opacity: 0 }}
      animate={{ scale: 1, opacity: dim ? 0.55 : 1 }}
      transition={reduce ? { duration: 0 } : { ...springGrow, delay }}
    >
      {isBest && <circle cx={cx} cy={cy} r={R + 5} fill="none" stroke="var(--accent)" strokeWidth={1.5} opacity={0.5} />}
      {isSelected && <circle cx={cx} cy={cy} r={R + 2} fill="none" stroke="var(--primary)" strokeWidth={2} />}
      <circle cx={cx} cy={cy} r={R} fill={isBest ? 'var(--accent)' : FILL[node.status]} stroke="var(--bg)" strokeWidth={2} />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize={10} fill="var(--bg)" fontWeight={600}>
        {node.val != null ? Math.round(node.val * 100) : '·'}
      </text>
      <text x={cx} y={cy + R + 14} textAnchor="middle" fontSize={9} fill="var(--muted)">
        {shortId(node.id)}
      </text>
    </motion.g>
  )
}

function shortId(id: string): string {
  if (id === 'seed') return 'seed'
  const m = id.match(/(\d+)$/)
  return m ? `#${parseInt(m[1], 10)}` : id.slice(0, 6)
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}
