/** Derive "what helped / what didn't" insights from the graph + memory + rollouts. */
import type { GraphNode, MemoryResult, RolloutDetail, RunDetail } from './types'

export interface HelpedItem {
  id: string
  delta: number
  val: number
}

/** Accepted candidates ranked by their improvement over their parent (desc). */
export function whatHelped(graph: RunDetail['graph']): HelpedItem[] {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))
  const out: HelpedItem[] = []
  for (const n of graph.nodes) {
    if (n.status !== 'accepted' || n.val == null) continue
    const parent = n.parent ? byId.get(n.parent) : undefined
    const base = parent?.val ?? null
    if (base == null) continue
    out.push({ id: n.id, delta: n.val - base, val: n.val })
  }
  return out.sort((a, b) => b.delta - a.delta)
}

export interface DeadEnd {
  reason: string
  count: number
  examples: string[]
}

/** Rejected reasons, deduped with occurrence counts (the "what not to try" list). */
export function deadEnds(rejected: MemoryResult['rejected']): DeadEnd[] {
  const map = new Map<string, DeadEnd>()
  for (const r of rejected) {
    const key = normalizeReason(r.reason)
    const cur = map.get(key) ?? { reason: key, count: 0, examples: [] }
    cur.count += 1
    if (cur.examples.length < 3) cur.examples.push(r.candidate_id)
    map.set(key, cur)
  }
  return [...map.values()].sort((a, b) => b.count - a.count)
}

/** Collapse numeric noise so near-identical gate reasons group together. */
export function normalizeReason(reason: string): string {
  return (reason || 'rejected')
    .replace(/-?\d+\.\d+/g, 'N')
    .replace(/-?\d+/g, 'N')
    .trim()
}

/** Aggregate tool-call frequency across a set of rollout details. */
export function toolUsage(rollouts: RolloutDetail[]): { name: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const r of rollouts) {
    for (const t of r.rollout?.tool_calls ?? []) {
      const n = String(t?.name ?? 'unknown')
      counts.set(n, (counts.get(n) ?? 0) + 1)
    }
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

/** A short human narrative of the run for the Insights header. */
export function narrative(detail: RunDetail): string {
  const s = detail.summary
  const counts = s.counts
  const accepted = counts?.accepted ?? 0
  const rejected = counts?.rejected ?? 0
  const pieces: string[] = []
  if (s.baseline_val != null && s.best_val != null) {
    const d = ((s.best_val - s.baseline_val) * 100).toFixed(1)
    pieces.push(
      `Starting from a ${(s.baseline_val * 100).toFixed(1)}% baseline, the search reached ` +
        `${(s.best_val * 100).toFixed(1)}% (+${d} points)`,
    )
  }
  pieces.push(`after ${accepted + rejected} iterations (${accepted} accepted, ${rejected} rejected)`)
  if (s.test_reward != null) {
    pieces.push(`The best candidate scored ${(s.test_reward * 100).toFixed(1)}% on the sealed test set`)
  }
  return pieces.join('. ') + '.'
}

export function statusOf(node: GraphNode): GraphNode['status'] {
  return node.status
}
