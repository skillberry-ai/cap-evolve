/** Derive the cumulative-best (running max) stair series from graph nodes. */
import type { GraphNode } from './types'

export interface CurvePoint {
  iteration: number
  val: number | null // this candidate's own val (for the scatter)
  best: number // running best so far (for the stair line)
  id: string
  status: GraphNode['status']
  isRecord: boolean // this point set a new running best
}

/**
 * Order nodes by iteration and compute the running best. Nodes without a numeric
 * `val` are skipped (no scatter point and no effect on the running best).
 */
export function cumulativeBest(nodes: GraphNode[]): CurvePoint[] {
  const ordered = [...nodes]
    .filter((n) => typeof n.val === 'number')
    .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))

  const out: CurvePoint[] = []
  let best = Number.NEGATIVE_INFINITY
  for (const n of ordered) {
    const v = n.val as number
    const isRecord = v > best
    if (isRecord) best = v
    out.push({
      iteration: n.iteration ?? out.length,
      val: v,
      best,
      id: n.id,
      status: n.status,
      isRecord,
    })
  }
  return out
}
