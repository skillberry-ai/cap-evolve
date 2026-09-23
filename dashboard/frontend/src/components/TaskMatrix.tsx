import { useMemo, useState } from 'react'
import type { GraphNode, RunSummaryDetail, ScreenRow } from '../lib/types'
import { Card } from './ui/Card'
import { VerdictBadge } from './StatusBadge'
import { cn } from '../lib/cn'

/** A screen's per-task rewards, read as a synthetic column — same shape as a full-val
 *  node's `per_task`, so it renders identically and reuses the "not run" hatched cell
 *  for every task outside its subset. `kind: 'screen'` keeps it out of anything that
 *  treats a column as a gated candidate (Candidates table, lineage tree, gate log). */
function screenToNode(s: ScreenRow): GraphNode {
  // Per-cell delta vs the screen's own reference, from `paired.deltas` — the number the
  // screen actually decided on. Prefixed onto the existing per-task feedback (if any)
  // rather than replacing it, so nothing recorded is lost.
  const deltas = s.delta_by_task ?? {}
  const feedback: Record<string, string> = {}
  for (const [tid, fb] of Object.entries(s.feedback ?? {})) feedback[tid] = fb
  for (const [tid, d] of Object.entries(deltas)) {
    const line = `Δ vs ${s.reference ?? 'reference'}: ${d > 0 ? '+' : ''}${d.toFixed(3)}`
    feedback[tid] = feedback[tid] ? `${line} — ${feedback[tid]}` : line
  }
  return {
    id: s.screen_tag,
    parent: s.reference ?? null,
    children: [],
    status: 'screened',
    val: null,
    // The screen's own aggregate — its mean_delta/se, NOT a mean of per_task (that
    // would silently compute a different, unweighted number for the same decision).
    stderr: s.se,
    per_task: s.per_task ?? {},
    feedback,
    fixed: s.fixed,
    broke: s.regressed,
    kind: 'screen',
    reason: s.mean_delta == null ? s.rationale ?? null
      : `subset Δ̄ ${s.mean_delta > 0 ? '+' : ''}${s.mean_delta.toFixed(4)}` +
        (s.se != null ? ` ± ${s.se.toFixed(4)}` : '') +
        ` → ${s.decision ?? '—'}${s.inconclusive ? ' (inconclusive)' : ''}`,
  }
}

/** Reward → cell class. `null` (never run) is visually distinct from 0 (ran, failed):
 *  a hatched empty cell, not a dark red one. Missing must never read as measured. */
function cellFor(v: number | null | undefined) {
  // Solid token colours only. A Tailwind opacity modifier over a `var()` colour silently
  // produces no declaration in this setup, which is how "fail" cells rendered invisible
  // and made a failing task look like a task that never ran.
  // The exact reward is rendered as visible text (not just colour) so two cells of the
  // same verdict but different scores (e.g. two "partial"s) aren't visually identical.
  const glyph = v == null ? '·' : v.toFixed(2)
  if (v == null) return { cls: 'bg-surface-3 border border-dashed border-border-strong',
                          label: 'not run', glyph }
  if (v >= 0.999) return { cls: 'bg-accepted', label: 'pass', glyph }
  if (v <= 0.001) return { cls: 'bg-rejected', label: 'fail', glyph }
  return { cls: 'bg-accent', label: 'partial', glyph }
}

/** Round-robin colours for the thin band that groups same-round columns — cycles so an
 *  arbitrary number of rounds still reads as alternating, not one repeated pair. Solid
 *  tokens only (no opacity modifier): a Tailwind opacity modifier over one of this
 *  project's `var()` colours silently produces no declaration (see `cellFor` above) —
 *  harmless here since the band is a 6px strip, not a wash over the column body. */
const ROUND_BAND_CLASSES = ['bg-primary', 'bg-accent', 'bg-indecisive']

/** Consecutive columns sharing the same (non-null) `round_id` collapse into one group,
 *  so the header can render a single spanning band over candidates round.py gated
 *  together. A column with no `round_id` (not gated via round.py) is its own group. */
function groupByRound(cols: GraphNode[]): { round_id: string | null; cols: GraphNode[] }[] {
  const groups: { round_id: string | null; cols: GraphNode[] }[] = []
  for (const n of cols) {
    const rid = n.round_id ?? null
    const last = groups[groups.length - 1]
    if (last && rid != null && last.round_id === rid) last.cols.push(n)
    else groups.push({ round_id: rid, cols: [n] })
  }
  return groups
}

/**
 * Per-task × per-candidate outcomes — the panel that makes churn visible.
 *
 * Two candidates can share an identical mean while passing different tasks; a single
 * aggregate score hides that completely. Rows are the tasks (worst mean first), columns
 * are the candidates in iteration order, and the seed column is the baseline to read
 * across from. Works for every algorithm: it needs only per-task rewards, and an
 * algorithm that evaluates a SUBSET (agent-optimize) simply leaves the rest "not run".
 *
 * `selectedId` narrows the rows to exactly the task ids present in that candidate's own
 * `per_task` — the same sparse map that already means "not run" for an absent key, so no
 * separate subset/screen field is needed to know what a candidate actually touched. No
 * selection (or a candidate with no per_task) falls back to the full task universe.
 */
export function TaskMatrix({
  summary,
  nodes,
  selectedId,
  screens,
}: {
  summary: RunSummaryDetail
  nodes: GraphNode[]
  selectedId?: string | null
  /** agent-optimize's cheap screens — subset evals that ran BEFORE full val, and would
   *  otherwise never appear here since they earn no graph node of their own. */
  screens?: ScreenRow[]
}) {
  const [hover, setHover] = useState<{ task: string; node: GraphNode } | null>(null)

  const cols = useMemo(() => {
    const candidateCols = nodes
      .filter((n) => Object.keys(n.per_task ?? {}).length > 0)
      .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
    const screenCols = (screens ?? [])
      .filter((s) => Object.keys(s.per_task ?? {}).length > 0)
      .map(screenToNode)
    return [...candidateCols, ...screenCols]
  }, [nodes, screens])

  const selectedNode = useMemo(
    () => (selectedId ? cols.find((n) => n.id === selectedId) : undefined),
    [cols, selectedId],
  )
  const selectedTaskIds = selectedNode ? Object.keys(selectedNode.per_task ?? {}) : null

  const rows = useMemo(() => {
    if (selectedTaskIds && selectedTaskIds.length > 0) {
      const mean = (t: string) => selectedNode!.per_task?.[t] ?? -1
      return [...selectedTaskIds].sort((a, b) => mean(a) - mean(b))
    }
    const ids = new Set(summary.tasks ?? [])
    for (const n of cols) for (const t of Object.keys(n.per_task ?? {})) ids.add(t)
    const mean = (t: string) => {
      const vals = cols.map((n) => n.per_task?.[t]).filter((v): v is number => v != null)
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : -1
    }
    return [...ids].sort((a, b) => mean(a) - mean(b))
  }, [summary.tasks, cols, selectedTaskIds, selectedNode])

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
  const roundGroups = useMemo(() => groupByRound(cols), [cols])
  const hasRounds = roundGroups.some((g) => g.round_id != null)

  return (
    <div className="space-y-4">
      {selectedTaskIds && selectedTaskIds.length > 0 && (
        <Card className="border-primary/40 bg-primary-soft">
          <p className="p-3.5 text-[12px] leading-relaxed text-muted-strong">
            Showing <span className="font-medium text-foreground">{selectedTaskIds.length}</span>{' '}
            task(s) — the subset <span className="font-mono">{selectedId}</span> was actually
            evaluated on. Select a different candidate, or deselect it, to see the full task
            universe.
          </p>
        </Card>
      )}
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
              {hasRounds && (
                <tr>
                  <th className="sticky left-0 z-10 bg-surface" />
                  {roundGroups.map((g, i) => (
                    <th
                      key={g.round_id ?? `solo-${i}`}
                      colSpan={g.cols.length}
                      title={g.round_id ? `gated together by round.py: ${g.round_id}` : undefined}
                      className={cn(
                        'h-1.5 rounded-[2px] p-0',
                        g.round_id ? ROUND_BAND_CLASSES[i % ROUND_BAND_CLASSES.length] : '',
                      )}
                    />
                  ))}
                </tr>
              )}
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
                    const fixed = n.fixed?.includes(t)
                    const broke = n.broke?.includes(t)
                    return (
                      <td key={n.id} className="p-0">
                        <button
                          type="button"
                          onMouseEnter={() => setHover({ task: t, node: n })}
                          onFocus={() => setHover({ task: t, node: n })}
                          onMouseLeave={() => setHover(null)}
                          onBlur={() => setHover(null)}
                          aria-label={`${t} on ${n.id}: ${c.label}${v != null ? ` (${v.toFixed(3)})` : ''}${
                            fixed ? ' — fixed vs parent' : broke ? ' — broke vs parent' : ''
                          }`}
                          className={cn(
                            'relative flex h-6 w-7 cursor-pointer items-center justify-center rounded-[3px]',
                            // Solid ring colour, no opacity modifier (see ROUND_BAND_CLASSES
                            // above for why one silently renders nothing in this setup).
                            // fixed/broke and :hover both set the same --tw-ring-color custom
                            // property, so a hover utility on top of a fixed/broke ring class
                            // would win by pseudo-class specificity and hide the marker on the
                            // exact interaction used to inspect it — one ring colour per state
                            // (fixed/broke takes priority; hover only applies otherwise).
                            'text-[9px] text-muted transition-shadow duration-150',
                            (fixed || broke) && 'ring-1 ring-inset',
                            fixed && 'ring-accepted',
                            broke && 'ring-rejected',
                            !fixed && !broke && 'hover:ring-2 hover:ring-border-strong',
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

        {/* Fixed min-height, always in flow: a cell's detail used to be inserted only on
            hover, and its height varied with feedback length — growing/shrinking the card
            shifted every element below it as the mouse moved across the grid ("jumping").
            Reserving the height up front (and never conditionally unmounting) keeps the
            layout stable regardless of which cell is hovered. */}
        <div className="min-h-[64px] border-t border-border bg-surface-2 px-3.5 py-2.5 text-[12px]">
          {hover ? (
            <>
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
            </>
          ) : (
            <span className="text-muted">Hover a cell for its reward and feedback.</span>
          )}
        </div>
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
              {/* A screen's decision was made on Δ̄ vs its reference, not on the raw
                  subset mean above — show the number it actually decided on. A real
                  candidate's `reason` is the gate/agent's own accept-or-reject note —
                  equally worth showing, and previously hidden here for every non-screen
                  column even though the node already carries it. */}
              {n.reason && (
                <span
                  className="tnum text-muted"
                  title={n.kind === 'screen'
                    ? "This screen's own aggregate — the statistic it actually gated on."
                    : 'The gate/agent note recorded for this decision.'}
                >
                  {n.reason}
                </span>
              )}
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
