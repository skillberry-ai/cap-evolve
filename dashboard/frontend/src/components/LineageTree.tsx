import { useState } from 'react'
import { motion } from 'framer-motion'
import type { RunGraph, GraphNode, Coverage, EvalState } from '../lib/types'
import { layoutLineage, type LaidNode } from '../lib/lineage'
import { pct } from '../lib/format'
import { coverageBadge, isPartial } from '../lib/coverage'
import { prefersReducedMotion, springGrow } from '../lib/motion'
import { Card } from './ui/Card'

const COL_W = 120
const ROW_H = 76
const PAD = 32
const R = 18

export const FILL: Record<GraphNode['status'], string> = {
  seed: 'var(--seed)',
  accepted: 'var(--accepted)',
  rejected: 'var(--rejected)',
  indecisive: 'var(--indecisive)',
  failed: 'var(--muted)',
  // A screen never earns a real graph node (see TaskMatrix's synthetic column), so this
  // is unreachable here — the map must stay exhaustive over NodeStatus regardless.
  screened: 'var(--muted)',
}

/** Best-path-as-spine lineage: the winning chain reads as a flat amber line
 * across the top; off-spine candidates hang below with L-connectors.
 *
 * Selection is controlled by the parent when `selectedId`/`onSelectId` are given, so the
 * Tasks tab (a sibling of this panel, not a child) can react to the same click — falls
 * back to local state so the panel still works standalone. */
export function LineageTree({
  graph,
  selectedId,
  onSelectId,
}: {
  graph: RunGraph
  selectedId?: string | null
  onSelectId?: (id: string) => void
}) {
  const layout = layoutLineage(graph)
  const [localSelected, setLocalSelected] = useState<string | null>(graph.best_id)
  const selected = selectedId !== undefined ? selectedId : localSelected
  const setSelected = onSelectId ?? setLocalSelected
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
  const parentIdx = new Map<string, number>()
  for (const e of layout.edges) if (!parentIdx.has(e.from)) parentIdx.set(e.from, parentIdx.size)
  const sel = selected ? pos.get(selected) : undefined
  const selParent = sel?.parent ? pos.get(sel.parent) : undefined

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-4 text-xs text-muted">
        <Legend color="var(--accent)" label="best path" />
        <Legend color="var(--accepted)" label="accepted" />
        <Legend color="var(--rejected)" label="rejected" />
        <Legend color="var(--seed)" label="seed" />
        <Legend color="var(--muted)" label="merge edge" dashed />
        <span className="inline-flex items-center gap-3" data-testid="state-legend">
          <span>solid = full val</span><span>ring = k/N tasks</span><span>half = screened</span><span>dashed = not run</span>
        </span>
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
            // Each parent gets its own trunk x-offset and colour, so siblings of different
            // parents sharing a column stay attributable; a "from #n" label sits at the child.
            const pi = parentIdx.get(e.from) ?? 0
            const trunk = x1 + 14 + (pi % 5) * 6
            const d = `M ${x1} ${y1} H ${Math.min(trunk, x2 - R - 6)} V ${y2} H ${x2}`
            const edgeColor = e.onSpine ? 'var(--accent)' : e.merge ? 'var(--muted)' : `var(--series-${(pi % 5) + 1})`
            return (
              <motion.path
                key={`${e.from}-${e.to}-${e.merge ? 'merge' : 'derive'}`}
                d={d}
                fill="none"
                stroke={edgeColor}
                data-from={e.from}
                strokeWidth={e.onSpine ? 2.5 : 1.5}
                strokeDasharray={e.merge ? '4 3' : undefined}
                initial={reduce ? false : { pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: reduce ? 0 : 0.4 }}
              />
            )
          })}

          {/* which parent each child hangs from */}
          {layout.edges.map((e) => {
            const b = pos.get(e.to)!
            if (e.onSpine) return null
            return (
              <text key={`lbl-${e.from}-${e.to}-${e.merge ? 'm' : 'd'}`} x={x(b.col) - R - 4} y={y(b.row) - 4} textAnchor="end" fontSize={8} fill="var(--muted-strong)" data-testid="edge-label">
                {e.merge ? 'merge ' : ''}from {shortId(e.from)}
              </text>
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
            {sel.evalState && <span className="text-muted">· {sel.evalState}{sel.coverage ? ` (${coverageLabel(sel.coverage)})` : ''}</span>}
            {sel.id === graph.best_id && <span className="text-accent">· champion</span>}
            {sel.changeType && <ChangeTypeBadge changeType={sel.changeType} />}
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
          {(sel.subset || sel.clusterIds) && (
            <div className="mt-1 text-xs text-muted">
              {sel.subset && `screened on ${sel.subset.task_ids.length} task(s)${sel.subset.tier != null ? ` (tier ${sel.subset.tier})` : ''}`}
              {sel.subset && sel.clusterIds && ' · '}
              {sel.clusterIds && `clusters: ${sel.clusterIds.join(', ')}`}
            </div>
          )}
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
  const dim = node.status === 'failed'
  const partial = isPartial(node)
  const badge = coverageBadge(node)
  const glyph = node.status === 'accepted' ? '✓' : node.status === 'rejected' ? '✗' : null
  const state = node.evalState
  const cov = node.coverage
  const ring = badge ?? (state === 'partial' && cov ? coverageLabel(cov) : null)
  return (
    <motion.g
      style={{ cursor: 'pointer', transformOrigin: `${cx}px ${cy}px` }}
      onClick={onSelect}
      tabIndex={0}
      role="button"
      aria-label={`${node.id} ${node.status} ${state ?? ''} ${node.val != null ? pct(node.val) : ''}`}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect()}
      initial={reduce ? false : { scale: 0.4, opacity: 0 }}
      animate={{ scale: 1, opacity: dim ? 0.55 : 1 }}
      transition={reduce ? { duration: 0 } : { ...springGrow, delay }}
    >
      {isBest && <circle cx={cx} cy={cy} r={R + 5} fill="none" stroke="var(--accent)" strokeWidth={1.5} opacity={0.5} />}
      {isSelected && <circle cx={cx} cy={cy} r={R + 2} fill="none" stroke="var(--primary)" strokeWidth={2} />}
      <NodeBody cx={cx} cy={cy} fill={isBest ? 'var(--accent)' : FILL[node.status]} state={state} />
      {/* a subset result never shows a bare percentage inside the node: the badge below carries it */}
      {!partial && (
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize={10} fill="#fff" stroke="rgba(0,0,0,0.45)" strokeWidth={2} paintOrder="stroke" fontWeight={700}>
          {node.val != null ? Math.round(node.val * 100) : '·'}
        </text>
      )}
      {glyph && (
        <text x={cx + R - 2} y={cy - R + 4} textAnchor="middle" fontSize={12} fontWeight={800} fill={node.status === 'accepted' ? 'var(--accepted)' : 'var(--rejected)'} stroke="var(--bg)" strokeWidth={3} paintOrder="stroke" data-testid="verdict-glyph">
          {glyph}
        </text>
      )}
      <text x={cx} y={cy + R + 14} textAnchor="middle" fontSize={9} fill="var(--muted)">
        {shortId(node.id)}
      </text>
      {ring && (
        <text x={cx} y={cy + R + 25} textAnchor="middle" fontSize={8} fill="var(--muted)" data-testid="coverage-mark">
          {ring}
        </text>
      )}
    </motion.g>
  )
}

export const coverageLabel = (c: Coverage) => `${c.n_tasks}/${c.n_val_tasks} tasks`

/** How much of val a candidate was measured on, encoded by PATTERN as well as colour so
 *  it reads for colour-blind reviewers: full = solid, partial = solid disc inside a
 *  lighter ring, screened = left half filled, unevaluated = dashed outline only. */
function NodeBody({ cx, cy, fill, state }: { cx: number; cy: number; fill: string; state?: EvalState }) {
  const stroke = { stroke: 'var(--bg)', strokeWidth: 2 }
  if (state === 'unevaluated')
    return <circle data-state={state} cx={cx} cy={cy} r={R} fill="var(--surface-2)" stroke={fill} strokeWidth={2} strokeDasharray="4 3" />
  if (state === 'screened')
    return (
      <g data-state={state}>
        <circle cx={cx} cy={cy} r={R} fill="var(--surface-2)" stroke={fill} strokeWidth={2} />
        <path d={`M ${cx} ${cy - R} A ${R} ${R} 0 0 0 ${cx} ${cy + R} Z`} fill={fill} />
      </g>
    )
  if (state === 'partial')
    return (
      <g data-state={state}>
        <circle cx={cx} cy={cy} r={R} fill="var(--surface-2)" stroke={fill} strokeWidth={3} />
        <circle cx={cx} cy={cy} r={R - 6} fill={fill} />
      </g>
    )
  return <circle data-state={state ?? 'full'} cx={cx} cy={cy} r={R} fill={fill} {...stroke} />
}

/** Small badge for a candidate's self-reported change_type (optional/nullable field —
 * absent on runs that predate it or never set it, see GraphNode.change_type). */
export function ChangeTypeBadge({ changeType }: { changeType: string }) {
  return (
    <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">
      {changeType}
    </span>
  )
}

function shortId(id: string): string {
  if (id === 'seed') return 'seed'
  const m = id.match(/(\d+)$/)
  return m ? `#${parseInt(m[1], 10)}` : id.slice(0, 6)
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {dashed ? (
        <svg width="12" height="4" aria-hidden>
          <line x1={0} y1={2} x2={12} y2={2} stroke={color} strokeWidth={1.5} strokeDasharray="3 2" />
        </svg>
      ) : (
        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      )}
      {label}
    </span>
  )
}
