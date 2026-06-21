import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronRight, File as FileIcon, Folder, FolderOpen } from 'lucide-react'
import { api } from '../lib/api'
import type { TreeEntry } from '../lib/types'
import { compactNum } from '../lib/format'
import { easeEnter } from '../lib/motion'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'
import { cn } from '../lib/cn'

/** A generic, format-agnostic browser of the run directory — the actual memory dir
 * and anything else on disk (candidates, work tree, store). Expand/collapse folders;
 * click a file to view its (size-capped, redacted) contents. No schema assumed. */
export function FileTree({ runId }: { runId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['tree', runId],
    queryFn: ({ signal }) => api.tree(runId, '', signal),
  })
  const [selected, setSelected] = useState<string | null>(null)

  // Default to a "memory" dir if present (what the user most wants to see).
  const entries = data?.entries ?? []
  const memoryFirst = useMemo(
    () => [...entries].sort((a, b) => Number(b.name === 'memory') - Number(a.name === 'memory')),
    [entries],
  )

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <Card className="p-3">
        <h3 className="mb-2 px-1 text-sm font-medium">Run directory</h3>
        {isLoading && <Skeleton className="h-48 w-full" />}
        {!isLoading && entries.length === 0 && (
          <p className="py-6 text-center text-sm text-muted">Empty run directory.</p>
        )}
        <ul className="text-sm">
          {memoryFirst.map((e) => (
            <TreeNode key={e.path} entry={e} depth={0} selected={selected} onSelect={setSelected} />
          ))}
        </ul>
        {data?.truncated && (
          <p className="mt-2 px-1 text-[11px] text-muted">Listing truncated (very large tree).</p>
        )}
      </Card>
      <Card className="p-3">
        <FileView runId={runId} path={selected} />
      </Card>
    </div>
  )
}

function TreeNode({
  entry,
  depth,
  selected,
  onSelect,
}: {
  entry: TreeEntry
  depth: number
  selected: string | null
  onSelect: (p: string) => void
}) {
  const [open, setOpen] = useState(depth === 0 && entry.name === 'memory')
  const pad = { paddingLeft: `${depth * 14 + 4}px` }

  if (entry.type === 'file') {
    const active = selected === entry.path
    return (
      <li>
        <button
          type="button"
          onClick={() => onSelect(entry.path)}
          style={pad}
          className={cn(
            'flex w-full items-center gap-1.5 rounded px-1 py-1 text-left hover:bg-surface-2',
            active && 'bg-surface-2 text-accent',
          )}
        >
          <FileIcon size={14} className="shrink-0 text-muted" />
          <span className="truncate font-mono text-xs">{entry.name}</span>
          {entry.size != null && (
            <span className="tnum ml-auto pl-2 text-[10px] text-muted">{compactNum(entry.size)}B</span>
          )}
        </button>
      </li>
    )
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={pad}
        className="flex w-full items-center gap-1 rounded px-1 py-1 text-left hover:bg-surface-2"
      >
        <motion.span animate={{ rotate: open ? 90 : 0 }} transition={easeEnter} className="shrink-0">
          <ChevronRight size={14} className="text-muted" />
        </motion.span>
        {open ? <FolderOpen size={14} className="shrink-0 text-accent" /> : <Folder size={14} className="shrink-0 text-muted" />}
        <span className="truncate text-xs font-medium">{entry.name}</span>
      </button>
      <AnimatePresence initial={false}>
        {open && entry.children && entry.children.length > 0 && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={easeEnter}
            className="overflow-hidden"
          >
            {entry.children.map((c) => (
              <TreeNode key={c.path} entry={c} depth={depth + 1} selected={selected} onSelect={onSelect} />
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  )
}

function FileView({ runId, path }: { runId: string; path: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['file', runId, path],
    queryFn: ({ signal }) => api.file(runId, path!, signal),
    enabled: !!path,
  })

  if (!path) return <p className="py-12 text-center text-sm text-muted">Select a file to view its contents.</p>
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!data) return <p className="py-12 text-center text-sm text-muted">Couldn’t read file.</p>

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 border-b border-border pb-1">
        <span className="truncate font-mono text-xs">{data.path}</span>
        <span className="tnum ml-auto text-[10px] text-muted">{compactNum(data.size)}B</span>
      </div>
      {data.binary ? (
        <p className="py-10 text-center text-sm text-muted">Binary file — not shown.</p>
      ) : (
        <pre className="max-h-[60vh] overflow-auto rounded bg-background p-2 text-xs leading-relaxed">{data.text}</pre>
      )}
      {data.truncated && <p className="mt-1 text-[11px] text-muted">File truncated (size cap).</p>}
    </div>
  )
}
