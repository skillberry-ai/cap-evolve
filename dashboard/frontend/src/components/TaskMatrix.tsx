import { useMemo, useState } from 'react'
import type { GraphNode, RunSummaryDetail } from '../lib/types'
import { Card } from './ui/Card'
import { VerdictBadge } from './StatusBadge'
import { cn } from '../lib/cn'

/** Reward → cell class. `null` (never run) is visually distinct from 0 (ran, failed):
 *  a hatched empty cell, not a dark red one. Missing must never read as measured. */
function cellFor(v: number | null | undefined) {
  // Solid token colours only. A Tailwind opacity modifier over a `var()` colour silently
  // produces no declaration in this setup, which is how "fail" cells rendered invisible
  // and made a failing task look like a task that never ran.
  if (v == null) return { cls: 'bg-surface-3 border border-dashed border-border-strong',
                          label: 'not run', glyph: '·' }
  if (v >= 0.999) return { cls: 'bg-accepted', label: 'pass', glyph: '' }
  if (v <= 0.001) return { cls: 'bg-rejected', label: 'fail', glyph: '' }
  return { cls: 'bg-accent', label: 'partial', glyph: '' }
}

/**
 * Per-task × per-candidate outcomes — the panel that makes churn visible.
 *
 * Two candidates can share an identical mean while passing different tasks; a single
 * aggregate score hides that completely. Rows are the tasks (worst mean first), columns
 * are the candidates in iteration order, and the seed column is the baseline to read
 * across from. Works for every algorithm: it needs only per-task rewards, and an
 * algorithm that evaluates a SUBSET (agent-optimize) simply leaves the rest "not run".
 */
export function TaskMatrix({
  summary,
  nodes,
}: {
  summary: RunSummaryDetail
  nodes: GraphNode[]
}) {
  const [hover, setHover] = useState<{ task: string; node: GraphNode } | null>(null)

  const cols = useMemo(
    () =>
      nodes
        .filter((n) => Object.keys(n.per_task ?? {}).length > 0)
        .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0)),
    [nodes],
  )

  const rows = useMemo(() => {
    const ids = new Set(summary.tasks ?? [])
    for (const n of cols) for (const t of Object.keys(n.per_task ?? {})) ids.add(t)
    const mean = (t: string) => {
      const vals = cols.map((n) => n.per_task?.[t]).filter((v): v is number => v != null)
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : -1
    }
    return [...ids].sort((a, b) => mean(a) - mean(b))
  }, [summary.tasks, cols])

  if (cols.length === 0 || rows.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No per-task rewards were persisted for this run, so the pass/fail matrix has
          nothing to show. It appears as soon as rollouts land in{' '}
          <code>rollouts/val/</code>.
        </div>
      </Card>
    )
  }

  const churn = findChurn(cols)

  return (
    <div className="space-y-4">
      {churn.length > 0 && (
        <Card className="border-accent/40 bg-accent/[0.04]">
          <p className="p-3.5 text-[12px] leading-relaxed text-muted-strong">
            <span className="font-medium text-accent">Churn detected.</span>{' '}
            {churn.map((c) => `${c.a} ↔ ${c.b}`).join(', ')} scored the{' '}
            <em>identical mean</em> while passing <em>different tasks</em>. The aggregate
            says "no change"; the matrix below shows the work was not free.
          </p>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 p-3.5 xl:flex-row xl:items-start">
        <div className="scroll-x">
          <table className="border-separate border-spacing-[2px] text-[11px]">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-surface pr-2 text-left font-normal text-muted">
                  task
                </th>
                {cols.map((n) => (
                  <th key={n.id} className="px-0.5 pb-1 align-bottom">
                    <div
                      className="tnum mx-auto whitespace-nowrap text-[10px] text-muted"
                      style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                    >
                      {n.id}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t}>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 max-w-[190px] truncate bg-surface pr-2
                               text-left font-mono font-normal text-muted-strong"
                    title={t}
                  >
                    {t}
                  </th>
                  {cols.map((n) => {
                    const v = n.per_task?.[t]
                    const c = cellFor(v)
                    return (
                      <td key={n.id} className="p-0">
                        <button
                          type="button"
                          onMouseEnter={() => setHover({ task: t, node: n })}
                          onFocus={() => setHover({ task: t, node: n })}
                          onMouseLeave={() => setHover(null)}
                          onBlur={() => setHover(null)}
                          aria-label={`${t} on ${n.id}: ${c.label}${v != null ? ` (${v.toFixed(3)})` : ''}`}
                          className={cn(
                            'flex h-6 w-7 cursor-pointer items-center justify-center rounded-[3px]',
                            'text-[9px] text-muted transition-transform duration-150 hover:scale-110',
                            c.cls,
                          )}
                        >
                          {c.glyph}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ColumnSummary cols={cols} nTasks={rows.length} />
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-border px-3.5 py-2 text-[11px] text-muted">
          <Legend cls="bg-accepted">pass (1.0)</Legend>
          <Legend cls="bg-accent">partial</Legend>
          <Legend cls="bg-rejected">fail (0.0)</Legend>
          <Legend cls="bg-surface-3 border border-dashed border-border-strong">
            not run — missing, not zero
          </Legend>
          <span>rows worst-mean first</span>
        </div>

        {hover && (
          <div className="border-t border-border bg-surface-2 px-3.5 py-2.5 text-[12px]">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono">{hover.task}</span>
              <span className="text-muted">on</span>
              <span className="font-mono">{hover.node.id}</span>
              <VerdictBadge verdict={hover.node.status} />
              <span className="tnum text-muted">
                reward{' '}
                <span className="text-foreground">
                  {hover.node.per_task?.[hover.task]?.toFixed(3) ?? '—'}
                </span>
              </span>
            </div>
            {hover.node.feedback?.[hover.task] && (
              <p className="mt-1 line-clamp-3 text-[11px] leading-snug text-muted-strong">
                {hover.node.feedback[hover.task]}
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

/**
 * One line per column: its mean, its verdict, and the tasks it fixed and broke.
 *
 * The matrix answers "which cells changed"; this answers "so what" without making the
 * reader hover 60 cells to find out. `fixed`/`broke` are the run's own recorded lists —
 * absent when the run never recorded the movement, never inferred from the cells.
 */
function ColumnSummary({ cols, nTasks }: { cols: GraphNode[]; nTasks: number }) {
  const cands = cols.filter((n) => n.id !== 'seed')
  if (cands.length === 0) return null
  const mean = (n: GraphNode) => {
    const vs = Object.values(n.per_task ?? {})
    return vs.length ? vs.reduce((a, b) => a + b, 0) / vs.length : null
  }
  return (
    <div className="min-w-0 flex-1 xl:border-l xl:border-border xl:pl-4">
      <div className="eyebrow mb-1.5">per candidate</div>
      <ul className="space-y-1.5">
        {cands.map((n) => {
          const m = mean(n)
          return (
            <li key={n.id} className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 text-[11px]">
              <span className="font-mono text-[12px]">{n.id}</span>
              <VerdictBadge verdict={n.status} />
              <span className="tnum text-muted">
                {m == null
                  ? '—'
                  : `${(m * 100).toFixed(1)}% over ${Object.keys(n.per_task ?? {}).length} tasks`}
              </span>
              {/* A mean over a SUBSET is not a val score. Say so where the number is. */}
              {m != null && Object.keys(n.per_task ?? {}).length < nTasks && (
                <span
                  className="tnum text-indecisive"
                  title="Scored on a subset only (a cheap screen) — this mean is not a val score."
                >
                  subset of {nTasks}
                </span>
              )}
              {!!n.fixed?.length && <span className="tnum text-accepted">fixed {n.fixed.join(' ')}</span>}
              {!!n.broke?.length && <span className="tnum text-rejected">broke {n.broke.join(' ')}</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** Pairs with the same mean but a different set of passing tasks — pure churn. */
export function findChurn(nodes: GraphNode[]): { a: string; b: string }[] {
  const sig = (n: GraphNode) =>
    Object.entries(n.per_task ?? {})
      .filter(([, v]) => v >= 0.999)
      .map(([t]) => t)
      .sort()
      .join('|')
  const out: { a: string; b: string }[] = []
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i]
      const b = nodes[j]
      if (a.val == null || b.val == null) continue
      if (Math.abs(a.val - b.val) < 1e-9 && sig(a) !== sig(b)) out.push({ a: a.id, b: b.id })
    }
  }
  return out.slice(0, 4)
}

function Legend({ cls, children }: { cls: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className={cn('h-2.5 w-2.5 rounded-sm', cls)} />
      {children}
    </span>
  )
}
