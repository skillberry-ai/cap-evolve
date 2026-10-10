/** Helpers that keep partial / screened measurements from passing as full val scores, and
 *  that read lineage from schema-v2 `parents[]` (a node is never its own parent). */
import type { GraphNode } from './types'

type P = Pick<GraphNode, 'id' | 'parent' | 'parents'>

/** The comparison parent: first non-self entry of `parents[]`, else a non-self `parent`. */
export function parentOf(n: P): string | null {
  const p = (n.parents ?? []).find((x) => x && x !== n.id)
  if (p) return p
  return n.parent && n.parent !== n.id ? n.parent : null
}

/** True for any result not measured on the full val set. */
export function isPartial(n: Pick<GraphNode, 'eval_state' | 'coverage'>): boolean {
  if (n.eval_state === 'screened' || n.eval_state === 'partial' || n.eval_state === 'unevaluated') return true
  const c = n.coverage
  return !!c && c.n_val_tasks > 0 && c.n_tasks < c.n_val_tasks
}

/** "8/30 screened" / "12/30 partial", or null for a full (or unknown-coverage) result. */
export function coverageBadge(n: Pick<GraphNode, 'eval_state' | 'coverage'>): string | null {
  if (!isPartial(n)) return null
  const k = n.coverage ? `${n.coverage.n_tasks}/${n.coverage.n_val_tasks} ` : ''
  return `${k}${n.eval_state === 'unevaluated' ? 'not run' : (n.eval_state ?? 'partial')}`
}

/** The best val actually seen on a full measurement by an accepted candidate (or the seed),
 *  WITH its own id -- never paired with another candidate's number. */
export function bestSeen(nodes: GraphNode[]): { id: string; val: number } | null {
  let out: { id: string; val: number } | null = null
  for (const n of nodes) {
    if (typeof n.val !== 'number' || isPartial(n)) continue
    if (n.status !== 'accepted' && n.status !== 'seed') continue
    if (!out || n.val > out.val) out = { id: n.id, val: n.val }
  }
  return out
}
