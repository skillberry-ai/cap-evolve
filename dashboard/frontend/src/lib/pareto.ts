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
