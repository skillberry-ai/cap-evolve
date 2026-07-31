import { Tabs, type TabDef } from './ui/Tabs'
import { IterationsDiff } from './IterationsDiff'
import { GitDiff } from './GitDiff'
import { MemoryPanel } from './MemoryPanel'
import { FileTree } from './FileTree'
import type { RunGraph } from '../lib/types'

/**
 * "Changes & files" (#139): the one place to inspect what a candidate changed.
 *
 * Four top-level tabs — Iterations (candidate-vs-parent snapshot diff), Git diffs
 * (commit-to-commit), Memory (accepted/rejected history + candidate scratch), Files (the
 * raw run dir) — were four different file/diff surfaces the reader had to disambiguate
 * before knowing which one answered "what did this edit do". They are now sub-modes here,
 * in increasing distance from the edit itself: the diff, the commit, the optimizer's
 * memory of it, the bytes on disk.
 *
 * Nothing is deleted. Every panel still mounts, so every backend field it read still has
 * a reader — including `rejected.jsonl` / `history.jsonl` via MemoryPanel, which #212
 * confirmed are live consumers.
 */
const MODES: TabDef[] = [
  { id: 'candidate', label: 'Candidate diff' },
  { id: 'commit', label: 'Commit diff' },
  { id: 'memory', label: 'Memory' },
  { id: 'files', label: 'Raw files' },
]

export function ChangesPanel({
  runId,
  graph,
  candidate,
  mode,
  onModeChange,
}: {
  runId: string
  graph: RunGraph
  /** #139 cross-link: the candidate to preselect in the diff/memory sub-modes. */
  candidate?: string | null
  mode?: string
  onModeChange?: (mode: string) => void
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Everything a candidate changed — its diff against its parent, the real commit, what
        the optimizer remembered about it, and the raw run directory.
      </p>
      <Tabs tabs={MODES} value={mode} onChange={onModeChange}>
        {(active) =>
          active === 'commit' ? (
            <GitDiff runId={runId} />
          ) : active === 'memory' ? (
            <MemoryPanel runId={runId} graph={graph} candidate={candidate} />
          ) : active === 'files' ? (
            <FileTree runId={runId} />
          ) : (
            <IterationsDiff runId={runId} graph={graph} candidate={candidate} />
          )
        }
      </Tabs>
    </div>
  )
}
