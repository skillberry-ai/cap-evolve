/** Reward-vs-cost Pareto frontier over candidate graph nodes.
 *
 * A point is non-dominated when no OTHER point beats it on both axes at once:
 * reward (maximize) and cost (minimize). Ties on both axes do not dominate each other. */
import type { GraphNode } from './types'

export interface ParetoPoint {
  id: string
  cost: number
  reward: number
  status: GraphNode['status']
  parent: string | null
}

/** Candidate nodes with both a val (reward) and a cost_usd, as scatter points.
 * Nodes missing either axis are excluded — plotting a 0 for a missing cost would
 * misrepresent it as free. */
export function toParetoPoints(nodes: GraphNode[]): ParetoPoint[] {
  return nodes
    .filter((n) => n.val != null && n.cost_usd != null)
    .map((n) => ({ id: n.id, cost: n.cost_usd as number, reward: n.val as number,
                   status: n.status, parent: n.parent }))
}

/** Ids of the non-dominated (Pareto-optimal) points: maximize reward, minimize cost. */
export function paretoFrontier(points: ParetoPoint[]): Set<string> {
  const frontier = new Set<string>()
  for (const p of points) {
    const dominated = points.some(
      (o) =>
        o.id !== p.id &&
        o.cost <= p.cost &&
        o.reward >= p.reward &&
        (o.cost < p.cost || o.reward > p.reward),
    )
    if (!dominated) frontier.add(p.id)
  }
  return frontier
}

/** Utopia/nadir normalization (MOO survey, Marler & Arora 2004, eq. 7), approximated
 * from best/worst OBSERVED values across this run's own points rather than solved
 * exactly — the paper's own caveat that exact utopia computation can be prohibitively
 * expensive maps directly onto this project's $1-2/eval cost. For both reward
 * (maximize) and cost (minimize) the result is 0 at the utopia (best observed) point
 * and 1 at the nadir (worst observed) point, so the two axes become visually
 * comparable on one [0,1]-ish scale regardless of direction. */
export interface NormalizedParetoPoint extends ParetoPoint {
  rewardNorm: number
  costNorm: number
}

export function normalizePoints(points: ParetoPoint[]): NormalizedParetoPoint[] {
  if (points.length === 0) return []
  const costs = points.map((p) => p.cost)
  const rewards = points.map((p) => p.reward)
  const costUtopia = Math.min(...costs)
  const costNadir = Math.max(...costs)
  const rewardUtopia = Math.max(...rewards)
  const rewardNadir = Math.min(...rewards)
  const costSpan = costNadir - costUtopia
  const rewardSpan = rewardNadir - rewardUtopia // <= 0 (nadir is the LOWER reward)
  // `|| 0` also folds a `-0` result (e.g. a point exactly at the reward utopia, where
  // the division's sign flips to negative zero) back to plain `0`.
  return points.map((p) => ({
    ...p,
    costNorm: (costSpan !== 0 ? (p.cost - costUtopia) / costSpan : 0) || 0,
    rewardNorm: (rewardSpan !== 0 ? (p.reward - rewardUtopia) / rewardSpan : 0) || 0,
  }))
}
