import { describe, expect, it } from 'vitest'
import { toParetoPoints, paretoFrontier, normalizePoints } from '../lib/pareto'
import type { GraphNode } from '../lib/types'

function node(p: Partial<GraphNode> & { id: string }): GraphNode {
  return { parent: null, children: [], status: 'accepted', val: null, ...p }
}

describe('toParetoPoints', () => {
  it('excludes nodes missing val or cost_usd', () => {
    const nodes = [
      node({ id: 'a', val: 0.5, cost_usd: 1.0 }),
      node({ id: 'b', val: null, cost_usd: 1.0 }),
      node({ id: 'c', val: 0.5, cost_usd: null }),
    ]
    expect(toParetoPoints(nodes).map((p) => p.id)).toEqual(['a'])
  })
})

describe('paretoFrontier', () => {
  it('keeps a point no other point beats on both axes', () => {
    const points = toParetoPoints([
      node({ id: 'cheap_low', val: 0.5, cost_usd: 1 }),
      node({ id: 'expensive_high', val: 0.9, cost_usd: 5 }),
      node({ id: 'dominated', val: 0.4, cost_usd: 3 }), // worse reward AND worse cost than cheap_low
    ])
    const frontier = paretoFrontier(points)
    expect(frontier.has('cheap_low')).toBe(true)
    expect(frontier.has('expensive_high')).toBe(true)
    expect(frontier.has('dominated')).toBe(false)
  })

  it('treats equal points as mutually non-dominating', () => {
    const points = toParetoPoints([
      node({ id: 'a', val: 0.5, cost_usd: 1 }),
      node({ id: 'b', val: 0.5, cost_usd: 1 }),
    ])
    const frontier = paretoFrontier(points)
    expect(frontier.has('a')).toBe(true)
    expect(frontier.has('b')).toBe(true)
  })
})

describe('normalizePoints', () => {
  it('maps the best-observed point on each axis to 0 and the worst to 1', () => {
    const points = toParetoPoints([
      node({ id: 'cheap_low', val: 0.5, cost_usd: 1 }),    // utopia on cost, nadir on reward
      node({ id: 'expensive_high', val: 0.9, cost_usd: 5 }), // utopia on reward, nadir on cost
      node({ id: 'mid', val: 0.7, cost_usd: 3 }),
    ])
    const byId = Object.fromEntries(normalizePoints(points).map((p) => [p.id, p]))
    expect(byId.cheap_low.costNorm).toBe(0)
    expect(byId.cheap_low.rewardNorm).toBe(1)
    expect(byId.expensive_high.costNorm).toBe(1)
    expect(byId.expensive_high.rewardNorm).toBe(0)
    // mid-cost, mid-reward -> somewhere strictly between utopia and nadir on both axes.
    expect(byId.mid.costNorm).toBeGreaterThan(0)
    expect(byId.mid.costNorm).toBeLessThan(1)
    expect(byId.mid.rewardNorm).toBeGreaterThan(0)
    expect(byId.mid.rewardNorm).toBeLessThan(1)
  })

  it('does not divide by zero when every point ties on an axis', () => {
    const points = toParetoPoints([
      node({ id: 'a', val: 0.5, cost_usd: 2 }),
      node({ id: 'b', val: 0.5, cost_usd: 2 }),
    ])
    const byId = Object.fromEntries(normalizePoints(points).map((p) => [p.id, p]))
    expect(byId.a.costNorm).toBe(0)
    expect(byId.a.rewardNorm).toBe(0)
  })
})
