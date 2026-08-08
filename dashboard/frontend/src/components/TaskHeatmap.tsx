import { useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { GraphNode } from '../lib/types'
import { pct } from '../lib/format'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

/**
 * tasks × iterations pass/fail grid (#139).
 *
 * The single-file static dashboard (core/cap_evolve/dashboard.py §3) has had this chart
 * since day one; the SPA never did, which left `GraphNode.per_task` and
 * `GraphNode.feedback` exported by the backend with no reader in the SPA at all. This is
 * that reader, and it is the cross-link source the issue asks for: clicking a cell jumps
 * to that task's rollout for that candidate.
 *
 * Rendered as a real `<table>` of `<button>` cells rather than SVG rects, so cell
 * activation is keyboard-native (Enter/Space, visible focus ring from index.css) without
 * re-implementing any of it. Each cell states its outcome as a glyph and an aria-label as
 * well as a colour — colour is never the only signal.
 *
 * The WAI-ARIA *grid* pattern, not one tab stop per cell: a 50×50 run is 2500 cells, and
 * 2500 tab stops is a keyboard trap in practice. Roving tabIndex gives the whole grid one
 * stop; Arrow/Home/End move the active cell inside it.
 */

type Outcome = 'pass' | 'fail' | 'partial' | 'skip'

const CELL: Record<Outcome, { glyph: string; word: string; cls: string }> = {
  pass: { glyph: '✓', word: 'pass', cls: 'bg-accepted/25 text-accepted' },
  fail: { glyph: '✗', word: 'fail', cls: 'bg-rejected/25 text-rejected' },
  partial: { glyph: '~', word: 'partial', cls: 'bg-accent/25 text-accent' },
  skip: { glyph: '·', word: 'not run', cls: 'bg-surface-2 text-muted' },
}

function outcome(v: number | undefined): Outcome {
  if (v == null) return 'skip'
  if (v >= 0.999) return 'pass'
  if (v <= 0.001) return 'fail'
  return 'partial'
}

export function TaskHeatmap({
  nodes,
  tasks,
  onOpenRollout,
}: {
  nodes: GraphNode[]
  tasks: string[]
  /** Cross-link: open this task's rollout for this candidate in the Trajectories drawer. */
  onOpenRollout?: (task: string, candidate: string) => void
}) {
  // Only candidates that were actually scored per-task, oldest-first (left to right).
  const iters = useMemo(
    () =>
      nodes
        .filter((n) => n.per_task && Object.keys(n.per_task).length > 0)
        .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0)),
    [nodes],
  )

  // Worst-first rows: the tasks that keep failing are the ones worth looking at.
  const rows = useMemo(() => {
    const mean = (t: string) => {
      const vals = iters.map((it) => it.per_task?.[t]).filter((v): v is number => v != null)
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
    }
    return [...tasks].sort((a, b) => mean(a) - mean(b))
  }, [tasks, iters])

  // Roving tabIndex over the grid: one tab stop, arrows move within.
  const [pos, setAt] = useState<[number, number]>([0, 0])
  // Clamp on read: rows/iters can shrink under a live run and a stale index would leave the
  // grid with no tab stop at all.
  const at: [number, number] = [
    Math.min(pos[0], Math.max(0, rows.length - 1)),
    Math.min(pos[1], Math.max(0, iters.length - 1)),
  ]
  const gridRef = useRef<HTMLTableSectionElement>(null)
  const focusCell = (r: number, c: number) => {
    const rr = Math.max(0, Math.min(rows.length - 1, r))
    const cc = Math.max(0, Math.min(iters.length - 1, c))
    setAt([rr, cc])
    gridRef.current?.querySelector<HTMLElement>(`[data-cell="${rr}-${cc}"]`)?.focus()
  }
  const onGridKeyDown = (e: KeyboardEvent) => {
    const [r, c] = at
    const move: Record<string, [number, number]> = {
      ArrowRight: [r, c + 1],
      ArrowLeft: [r, c - 1],
      ArrowDown: [r + 1, c],
      ArrowUp: [r - 1, c],
      Home: [r, 0],
      End: [r, iters.length - 1],
      PageUp: [0, c],
      PageDown: [rows.length - 1, c],
    }
    const next = move[e.key]
    if (!next) return
    e.preventDefault()
    focusCell(next[0], next[1])
  }

  if (rows.length === 0 || iters.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No per-task scores yet — the pass/fail grid appears once a candidate is evaluated.
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <h3 className="text-sm font-medium">Per-task pass/fail across iterations</h3>
        <span className="text-xs text-muted">
          rows worst-first · arrow keys move, Enter opens that rollout
        </span>
      </div>

      <div className="overflow-x-auto">
        <table role="grid" className="text-left text-xs" data-testid="task-heatmap">
          <caption className="sr-only">
            Per-task reward for every evaluated candidate. Rows are tasks, worst mean reward
            first; columns are iterations. Each cell states pass, fail, partial or not run.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="px-1 py-1 font-medium text-muted">
                task
              </th>
              {iters.map((it) => (
                <th
                  key={it.id}
                  scope="col"
                  className="tnum px-0.5 py-1 text-center font-medium text-muted"
                  title={`${it.id} · ${it.status} · val ${pct(it.val)}`}
                >
                  {it.iteration ?? '—'}
                </th>
              ))}
            </tr>
          </thead>
          <tbody ref={gridRef} onKeyDown={onGridKeyDown}>
            {rows.map((t, ri) => (
              <tr key={t}>
                <th
                  scope="row"
                  className="max-w-[18ch] truncate py-0.5 pr-2 font-mono text-[11px] font-normal text-muted"
                  title={t}
                >
                  {t}
                </th>
                {iters.map((it, ci) => {
                  const v = it.per_task?.[t]
                  const o = outcome(v)
                  const { glyph, word, cls } = CELL[o]
                  const fb = it.feedback?.[t]
                  const label = `${t} at iteration ${it.iteration ?? '?'} (${it.id}): ${word}${
                    v != null ? `, reward ${v.toFixed(3)}` : ''
                  }${fb ? ` — ${fb}` : ''}`
                  const linkable = o !== 'skip' && !!onOpenRollout
                  return (
                    <td key={it.id} role="gridcell" className="p-[1px]">
                      {/* aria-disabled, not `disabled`: a disabled button is unfocusable,
                          which would punch holes in the arrow-key walk. */}
                      <button
                        type="button"
                        data-cell={`${ri}-${ci}`}
                        aria-label={label}
                        title={label}
                        aria-disabled={!linkable}
                        tabIndex={at[0] === ri && at[1] === ci ? 0 : -1}
                        onFocus={() => setAt([ri, ci])}
                        onClick={() => linkable && onOpenRollout(t, it.id)}
                        className={cn(
                          'flex h-4 w-5 items-center justify-center rounded-[2px] text-[9px] leading-none',
                          cls,
                          linkable ? 'hover:ring-1 hover:ring-primary' : 'cursor-default',
                        )}
                      >
                        <span aria-hidden>{glyph}</span>
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        {(['pass', 'fail', 'partial', 'skip'] as Outcome[]).map((o) => (
          <span key={o} className="inline-flex items-center gap-1">
            <span
              aria-hidden
              className={cn('inline-flex h-4 w-5 items-center justify-center rounded-[2px] text-[9px]', CELL[o].cls)}
            >
              {CELL[o].glyph}
            </span>
            {CELL[o].word}
          </span>
        ))}
      </div>
    </Card>
  )
}
