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

/** Render one diff file: a header (path + ± counts) and the row body. */
export function DiffFileView({ file }: { file: DiffFile }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 border-b border-border pb-1">
        <span className="truncate font-mono text-xs">{file.path}</span>
        <span className="tnum ml-auto text-xs text-accepted">+{file.added}</span>
        <span className="tnum text-xs text-rejected">−{file.removed}</span>
      </div>
      <pre className="overflow-x-auto rounded-b bg-background text-xs leading-relaxed">
        {file.rows.map((r, i) => (
          <div key={i} className={cn('px-2', ROW_CLASS[r.t])}>
            {r.l || ' '}
          </div>
        ))}
      </pre>
    </div>
  )
}
