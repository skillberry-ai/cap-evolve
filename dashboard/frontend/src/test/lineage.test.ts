import { describe, expect, it } from 'vitest'
import { layoutLineage } from '../lib/lineage'
import type { GraphNode, RunGraph } from '../lib/types'

function node(p: Partial<GraphNode> & { id: string }): GraphNode {
  return { parent: null, children: [], status: 'accepted', val: null, ...p }
}

// seed -> c1 (best) ; c2 is an off-spine rejected child of c1
const GRAPH: RunGraph = {
  root: 'seed',
  best_id: 'c1',
  nodes: [
    node({ id: 'seed', status: 'seed', val: 0.2, iteration: 0 }),
    node({ id: 'c1', parent: 'seed', status: 'accepted', val: 0.7, iteration: 1 }),
    node({ id: 'c2', parent: 'c1', status: 'rejected', val: 0.6, iteration: 2 }),
  ],
}

describe('layoutLineage', () => {
  it('puts the root→best chain on the spine (row 0)', () => {
    const { nodes } = layoutLineage(GRAPH)
    const onSpine = nodes.filter((n) => n.onSpine).map((n) => n.id).sort()
    expect(onSpine).toEqual(['c1', 'seed'])
    expect(nodes.find((n) => n.id === 'seed')!.row).toBe(0)
    expect(nodes.find((n) => n.id === 'c1')!.row).toBe(0)
  })

  it('drops off-spine candidates to a branch lane (row > 0)', () => {
    const { nodes } = layoutLineage(GRAPH)
    const c2 = nodes.find((n) => n.id === 'c2')!
    expect(c2.onSpine).toBe(false)
    expect(c2.row).toBeGreaterThan(0)
  })

  it('assigns columns by depth from root', () => {
    const { nodes, cols } = layoutLineage(GRAPH)
    expect(nodes.find((n) => n.id === 'seed')!.col).toBe(0)
    expect(nodes.find((n) => n.id === 'c1')!.col).toBe(1)
    expect(nodes.find((n) => n.id === 'c2')!.col).toBe(2)
    expect(cols).toBe(3)
  })

  it('builds parent→child edges and marks spine edges', () => {
    const { edges } = layoutLineage(GRAPH)
    expect(edges).toContainEqual({ from: 'seed', to: 'c1', onSpine: true })
    expect(edges).toContainEqual({ from: 'c1', to: 'c2', onSpine: false })
  })

  it('handles an empty / best-less graph without throwing', () => {
    expect(layoutLineage({ root: 'seed', best_id: null, nodes: [] }).nodes).toEqual([])
  })
})
