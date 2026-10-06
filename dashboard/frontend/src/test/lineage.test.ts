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
    expect(edges).toContainEqual({ from: 'seed', to: 'c1', onSpine: true, merge: false })
    expect(edges).toContainEqual({ from: 'c1', to: 'c2', onSpine: false, merge: false })
  })

  it('handles an empty / best-less graph without throwing', () => {
    expect(layoutLineage({ root: 'seed', best_id: null, nodes: [] }).nodes).toEqual([])
  })
})

describe('layoutLineage merge edges', () => {
  // seed -> c1 -> c3; seed -> c2 (sibling); c4 merges c1 (parent) and c2 (merge_of)
  const MERGE_GRAPH: RunGraph = {
    root: 'seed',
    best_id: 'c4',
    nodes: [
      node({ id: 'seed', status: 'seed', val: 0.2, iteration: 0 }),
      node({ id: 'c1', parent: 'seed', status: 'accepted', val: 0.5, iteration: 1 }),
      node({ id: 'c2', parent: 'seed', status: 'accepted', val: 0.4, iteration: 1 }),
      node({ id: 'c4', parent: 'c1', merge_of: ['c1', 'c2'], status: 'accepted', val: 0.8, iteration: 2 }),
    ],
  }

  it('draws a second incoming edge for each merge_of id, distinct from the derive edge', () => {
    const { edges } = layoutLineage(MERGE_GRAPH)
    const derive = edges.find((e) => e.from === 'c1' && e.to === 'c4' && !e.merge)
    const merge = edges.find((e) => e.from === 'c2' && e.to === 'c4' && e.merge)
    expect(derive).toBeTruthy()
    expect(merge).toBeTruthy()
  })

  it('does not duplicate an edge when merge_of repeats the normal parent', () => {
    const { edges } = layoutLineage(MERGE_GRAPH)
    const fromC1 = edges.filter((e) => e.from === 'c1' && e.to === 'c4')
    expect(fromC1).toHaveLength(1)
  })

  it('a merge edge is never marked onSpine', () => {
    const { edges } = layoutLineage(MERGE_GRAPH)
    const merge = edges.find((e) => e.merge)!
    expect(merge.onSpine).toBe(false)
  })
})
