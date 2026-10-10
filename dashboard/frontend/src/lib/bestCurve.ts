/** Derive the cumulative-best (running max) stair series from graph nodes. */
import type { GraphNode } from './types'
import { coverageBadge, isPartial } from './coverage'

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
  /** "8/30 screened" etc. when this val is NOT a full-val measurement (never a record). */
  badge: string | null
}

/**
 * Order nodes by iteration and compute the running best. Nodes without a numeric
 * `val` are skipped (no scatter point and no effect on the running best).
 */
export function cumulativeBest(nodes: GraphNode[], bestId?: string | null, includePartial = false): CurvePoint[] {
  const ordered = [...nodes]
    .filter((n) => typeof n.val === 'number' && (includePartial || !isPartial(n)))
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
    const isRecord = !isPartial(n) && v > best && (n.status === 'accepted' || n.status === 'seed')
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
      badge: coverageBadge(n),
    })
  }
  const finalBest = out.length ? out[out.length - 1].best : null
  // The star sits on the run's selected champion (best_id) when it is plotted, so it always
  // agrees with the KPI tile; otherwise on the first point to reach the final running best.
  const champ = (bestId && out.find((p) => p.id === bestId)) || out.find((p) => p.isRecord && p.best === finalBest)
  if (champ) champ.isChampion = true
  return out
}
