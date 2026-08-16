import type { DiffFile } from '../lib/types'
import { cn } from '../lib/cn'

/** Shared diff row styling + file renderer used by IterationsDiff and GitDiff —
 * one source of truth for the diff markup so the views stay identical. */
export const ROW_CLASS = {
  add: 'bg-accepted/10 text-accepted',
  del: 'bg-rejected/10 text-rejected',
  hunk: 'text-primary',
  ctx: 'text-muted',
} as const

/**
 * Rows above which a file's body starts COLLAPSED behind its header.
 *
 * A per-iteration commit in a real run is the whole capability arriving at once: the
 * tau2-airline commits are ~2,500 rows each (`tools.py` alone is 780 of them), which
 * turned the Memory tab into a 12,000-pixel wall of green and buried the iteration list
 * and the memory panel above it. Candidate-vs-parent diffs — the edits you actually read
 * — are 14-51 rows and stay fully inline. Nothing is hidden, it just isn't the default,
 * and the ± counts in the always-visible header still say how big the file is.
 */
const INLINE_ROWS = 120
/**
 * ...and the same limit measured in characters, because rows alone is the wrong ruler.
 * A 5-row `rejected.jsonl` hunk carries 1,200-character lines; wrapping those (so none of
 * it is cut off) makes five rows twelve screen-inches tall. The real cost of a file is how
 * much text it is, not how many newlines are in it. 12,000 keeps a candidate-vs-parent
 * policy edit (7.6k-8.6k chars — the thing a reviewer came to read) fully inline.
 */
const INLINE_CHARS = 12_000

function Row({ row }: { row: DiffFile['rows'][number] }) {
  return (
    <div className={cn('whitespace-pre-wrap break-words pl-6 -indent-4 pr-2', ROW_CLASS[row.t])}>
      {row.l || ' '}
    </div>
  )
}

/** Render one diff file: a header (path + ± counts) and the row body. */
export function DiffFileView({ file }: { file: DiffFile }) {
  const header = (
    <>
      <span className="truncate font-mono text-xs">{file.path}</span>
      <span className="tnum ml-auto text-xs text-accepted">+{file.added}</span>
      <span className="tnum text-xs text-rejected">−{file.removed}</span>
    </>
  )
  {
    /* Rows WRAP rather than scroll sideways. `white-space: pre` inside an overflow-x
       container silently cut every long line at the card's edge — the policy diffs in a
       real prompt-optimization run are 200+ characters, so the half of each edit that
       mattered sat off-screen behind a scrollbar nobody scrolls (and invisible in any
       screenshot). The hanging indent keeps the +/− column readable when a line spills. */
  }
  const body = (
    <pre className="rounded-b bg-background text-xs leading-relaxed">
      {file.rows.map((r, i) => (
        <Row key={i} row={r} />
      ))}
    </pre>
  )

  const chars = file.rows.reduce((n, r) => n + (r.l?.length ?? 0), 0)
  if (file.rows.length <= INLINE_ROWS && chars <= INLINE_CHARS) {
    return (
      <div className="mb-4">
        <div className="flex items-center gap-2 border-b border-border pb-1">{header}</div>
        {body}
      </div>
    )
  }
  return (
    <details className="mb-4">
      <summary className="flex cursor-pointer items-center gap-2 border-b border-border pb-1 hover:text-foreground">
        {header}
        <span className="tnum shrink-0 text-[11px] text-muted">{file.rows.length} lines</span>
      </summary>
      {body}
    </details>
  )
}
