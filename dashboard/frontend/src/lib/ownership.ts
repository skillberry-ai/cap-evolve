/** Per-task ownership (issue #684 item 3/9): which candidate currently best-scores each
 * task — GEPA's per-instance ownership idea (Algorithm 2), computed client-side from the
 * per-task rewards every GraphNode already carries (`per_task`), the same data TaskMatrix
 * renders. No new backend field: `core/cap_evolve/task_ownership.py` (issue #684 item 3,
 * owned elsewhere) computes the equivalent `{owners, best_score, ownership_count}` shape
 * on-demand for `plan_round.py`'s branch planning, but writes nothing to graph.jsonl/
 * events.jsonl for the dashboard to read — so this mirrors its shape over data already
 * exported today, and can be swapped for a persisted field later without changing callers. */
import type { GraphNode } from './types'

export interface Ownership {
  /** task_id -> candidate ids tied at that task's best observed score, sorted. */
  owners: Record<string, string[]>
  /** task_id -> that best score. */
  bestScore: Record<string, number>
  /** candidate id -> number of tasks it owns (solely or tied) — GEPA's f[candidate]. */
  ownershipCount: Record<string, number>
}

/** Candidate nodes with at least one per-task score, in iteration order — the same
 * column set TaskMatrix builds its grid from. */
export function ownershipCandidates(nodes: GraphNode[]): GraphNode[] {
  return nodes
    .filter((n) => Object.keys(n.per_task ?? {}).length > 0)
    .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
}

export function computeOwnership(candidates: GraphNode[]): Ownership {
  const owners: Record<string, string[]> = {}
  const bestScore: Record<string, number> = {}
  const ownershipCount: Record<string, number> = {}
  const taskIds = new Set<string>()
  for (const n of candidates) for (const t of Object.keys(n.per_task ?? {})) taskIds.add(t)

  for (const t of taskIds) {
    let best = -Infinity
    for (const n of candidates) {
      const v = n.per_task?.[t]
      if (v != null && v > best) best = v
    }
    if (best === -Infinity) continue
    bestScore[t] = best
    owners[t] = candidates
      .filter((n) => n.per_task?.[t] === best)
      .map((n) => n.id)
      .sort()
    for (const cid of owners[t]) ownershipCount[cid] = (ownershipCount[cid] ?? 0) + 1
  }
  return { owners, bestScore, ownershipCount }
}

/** Deterministic categorical color by index — this project defines no per-candidate
 * palette (only status colors), so this is a simple hash-free HSL rotation. */
export function colorForIndex(i: number): string {
  const hue = (i * 47) % 360 // 47: coprime-ish with 360, spreads adjacent indices apart
  return `hsl(${hue}, 55%, 55%)`
}
