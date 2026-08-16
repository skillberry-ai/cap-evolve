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

describe('cumulativeBest — only a shippable capability is a "best"', () => {
  it('a REJECTED candidate with a higher raw val must not raise the stair', () => {
    // The real v4 run: two candidates scored a raw 0.5833 and were rejected on the
    // no-regression veto, while the run's actual best stayed the seed at 0.5667. The
    // chart read "best 58.3%" against a KPI tile reading "BEST VAL 56.7%" — the two
    // contradicted each other, and the chart was the one that was wrong. A rejected
    // capability is one you cannot ship, so it is not the best of anything.
    const nodes = [
      node({ id: 'seed', status: 'seed', val: 0.5667, iteration: 0 }),
      node({ id: 'cA_partial', status: 'rejected', val: 0.5833, iteration: 1 }),
      node({ id: 'cB_becabin', status: 'rejected', val: 0.5833, iteration: 2 }),
    ]
    const curve = cumulativeBest(nodes)
    expect(curve.map((p) => p.best)).toEqual([0.5667, 0.5667, 0.5667])
    expect(curve.map((p) => p.isRecord)).toEqual([true, false, false])
    // the rejected candidates still PLOT — they were measured, and hiding them would
    // be its own dishonesty
    expect(curve.map((p) => p.val)).toEqual([0.5667, 0.5833, 0.5833])
  })

  it('an accepted candidate does raise the stair', () => {
    const nodes = [
      node({ id: 'seed', status: 'seed', val: 0.20, iteration: 0 }),
      node({ id: 'c1', status: 'rejected', val: 0.90, iteration: 1 }),
      node({ id: 'c2', status: 'accepted', val: 0.40, iteration: 2 }),
    ]
    const curve = cumulativeBest(nodes)
    expect(curve.map((p) => p.best)).toEqual([0.20, 0.20, 0.40])
    expect(curve.at(-1)?.isChampion).toBe(true)
  })

  it('indecisive and failed never raise the stair either', () => {
    for (const status of ['indecisive', 'failed'] as const) {
      const curve = cumulativeBest([
        node({ id: 'seed', status: 'seed', val: 0.3, iteration: 0 }),
        node({ id: 'x', status, val: 0.99, iteration: 1 }),
      ])
      expect(curve.at(-1)?.best).toBe(0.3)
    }
  })
})
