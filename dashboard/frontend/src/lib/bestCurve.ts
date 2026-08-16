/** Derive the cumulative-best (running max) stair series from graph nodes. */
import type { GraphNode } from './types'

export interface CurvePoint {
  iteration: number
  val: number | null // this candidate's own val (for the scatter)
  best: number // running best so far (for the stair line)
  id: string
  status: GraphNode['status']
  isRecord: boolean // this point set a new running best
  /** Measured stderr of this candidate's val, or null when none was recorded. */
  stderr: number | null
  /** Exactly one point is the champion: the FIRST to reach the final best. Marking
   *  every point that merely ties it (three identical 0.750s in a real run) produced a
   *  row of stars and no champion. */
  isChampion: boolean
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
    // ONLY a candidate the gate accepted (or the seed) may move the running best. This
    // used to exclude `indecisive` alone, which let a REJECTED candidate raise the
    // stair: on a real run two candidates scored a raw 0.5833, were rejected on the
    // no-regression veto, and the chart then read "best 58.3%" while the run's actual
    // best was the seed at 56.7% — the KPI tile and the chart contradicted each other.
    // A rejected capability is one you cannot ship, so it is not a best of anything.
    const isRecord = v > best && (n.status === 'accepted' || n.status === 'seed')
    if (isRecord) best = v
    out.push({
      iteration: n.iteration ?? out.length,
      val: v,
      best,
      id: n.id,
      status: n.status,
      isRecord,
      stderr: n.stderr ?? null,
      isChampion: false,
    })
  }
  const finalBest = out.length ? out[out.length - 1].best : null
  const champ = out.find((p) => p.isRecord && p.best === finalBest)
  if (champ) champ.isChampion = true
  return out
}
