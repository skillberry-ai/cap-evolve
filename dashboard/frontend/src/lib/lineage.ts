/** Lay out the candidate graph as a best-path spine with branches hanging below. */
import type { RunGraph, GraphNode, EvalState, Coverage } from './types'

export interface LaidNode {
  id: string
  parent: string | null
  status: GraphNode['status']
  val: number | null
  reason: string | null
  onSpine: boolean
  col: number // x slot (by depth from root)
  row: number // y slot (0 = spine, >0 = branch lanes)
  subset?: { task_ids: string[]; tier: number | null } | null
  clusterIds?: string[]
  mergeOf?: string[]
  changeType?: string | null
  evalState?: EvalState
  coverage?: Coverage | null
  parents?: string[]
}

export interface LineageLayout {
  nodes: LaidNode[]
  edges: { from: string; to: string; onSpine: boolean; merge: boolean }[]
  cols: number
  rows: number
}

/** The root→best_id chain is the spine (row 0). Off-spine nodes drop to lanes
 * below, ordered by depth. Deterministic and dependency-free for unit testing. */
export function layoutLineage(graph: RunGraph): LineageLayout {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]))

  // Depth (column) from root via parent chain.
  const depthOf = (id: string): number => {
    let d = 0
    let cur = byId.get(id)
    const seen = new Set<string>()
    while (cur?.parent && byId.has(cur.parent) && !seen.has(cur.id)) {
      seen.add(cur.id)
      d += 1
      cur = byId.get(cur.parent)
    }
    return d
  }

  // Spine: walk parents from best_id back to root.
  const spine = new Set<string>()
  let cur = graph.best_id ? byId.get(graph.best_id) : undefined
  const guard = new Set<string>()
  while (cur && !guard.has(cur.id)) {
    spine.add(cur.id)
    guard.add(cur.id)
    cur = cur.parent ? byId.get(cur.parent) : undefined
  }

  // Assign rows: spine = 0; branches get the next free lane per column.
  const laneByCol = new Map<number, number>()
  const ordered = [...graph.nodes].sort(
    (a, b) => (a.iteration ?? 0) - (b.iteration ?? 0) || a.id.localeCompare(b.id),
  )

  const nodes: LaidNode[] = ordered.map((n) => {
    const col = depthOf(n.id)
    const onSpine = spine.has(n.id)
    let row = 0
    if (!onSpine) {
      const next = (laneByCol.get(col) ?? 0) + 1
      laneByCol.set(col, next)
      row = next
    }
    return {
      id: n.id,
      parent: n.parent,
      status: n.status,
      val: n.val,
      reason: n.reason ?? null,
      onSpine,
      col,
      row,
      subset: n.subset,
      clusterIds: n.cluster_ids,
      mergeOf: n.merge_of,
      changeType: n.change_type ?? null,
      evalState: n.eval_state,
      coverage: n.coverage ?? null,
      parents: n.parents,
    }
  })

  const byIdLaid = new Map(nodes.map((n) => [n.id, n]))
  const edges = nodes
    .filter((n) => n.parent && byId.has(n.parent))
    .map((n) => ({
      from: n.parent as string,
      to: n.id,
      onSpine: n.onSpine && spine.has(n.parent as string),
      merge: false,
    }))
  // merge_of: a second (or further) incoming edge from each co-parent, distinct from
  // the normal derive edge above — never on the spine (a merge result's spine parent is
  // `parent`, these are the extra lineage the spine doesn't follow).
  for (const n of ordered) {
    // schema v2 `parents[]` (merge results have 2+) and legacy `merge_of`, de-duplicated.
    for (const mergeParent of new Set([...(n.merge_of ?? []), ...(n.parents ?? [])])) {
      if (mergeParent !== n.parent && byIdLaid.has(mergeParent)) {
        edges.push({ from: mergeParent, to: n.id, onSpine: false, merge: true })
      }
    }
  }

  const cols = nodes.reduce((m, n) => Math.max(m, n.col), 0) + 1
  const rows = nodes.reduce((m, n) => Math.max(m, n.row), 0) + 1
  return { nodes, edges, cols, rows }
}
