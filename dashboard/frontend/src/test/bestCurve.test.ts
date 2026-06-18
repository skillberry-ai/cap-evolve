import { describe, expect, it } from 'vitest'
import { cumulativeBest } from '../lib/bestCurve'
import type { GraphNode } from '../lib/types'

function node(p: Partial<GraphNode>): GraphNode {
  return { id: 'x', parent: null, children: [], status: 'accepted', val: null, ...p }
}

describe('cumulativeBest', () => {
  it('computes a non-decreasing running best ordered by iteration', () => {
    const nodes = [
      node({ id: 'seed', status: 'seed', val: 0.2, iteration: 0 }),
      node({ id: 'c2', val: 0.5, iteration: 2 }),
      node({ id: 'c1', val: 0.4, iteration: 1 }),
      node({ id: 'c3', val: 0.3, iteration: 3 }),
    ]
    const curve = cumulativeBest(nodes)
    expect(curve.map((p) => p.id)).toEqual(['seed', 'c1', 'c2', 'c3'])
    expect(curve.map((p) => p.best)).toEqual([0.2, 0.4, 0.5, 0.5])
    expect(curve.map((p) => p.isRecord)).toEqual([true, true, true, false])
  })

  it('skips nodes without a numeric val', () => {
    const nodes = [
      node({ id: 'seed', val: 0.2, iteration: 0 }),
      node({ id: 'failed', val: null, iteration: 1 }),
      node({ id: 'c1', val: 0.6, iteration: 2 }),
    ]
    const curve = cumulativeBest(nodes)
    expect(curve.map((p) => p.id)).toEqual(['seed', 'c1'])
    expect(curve.at(-1)?.best).toBe(0.6)
  })

  it('returns an empty array for no scorable nodes', () => {
    expect(cumulativeBest([])).toEqual([])
    expect(cumulativeBest([node({ val: null })])).toEqual([])
  })
})
