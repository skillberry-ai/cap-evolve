import { describe, expect, it } from 'vitest'
import { computeOwnership, ownershipCandidates } from '../lib/ownership'
import type { GraphNode } from '../lib/types'

const node = (over: Partial<GraphNode> & { id: string }): GraphNode =>
  ({ parent: null, children: [], status: 'accepted', val: null, ...over }) as GraphNode

describe('computeOwnership', () => {
  it('assigns each task to its single best-scoring candidate', () => {
    const cands = ownershipCandidates([
      node({ id: 'cand_a', per_task: { t1: 1.0, t2: 0.2 } }),
      node({ id: 'cand_b', per_task: { t1: 0.3, t2: 0.9 } }),
    ])
    const o = computeOwnership(cands)
    expect(o.owners.t1).toEqual(['cand_a'])
    expect(o.owners.t2).toEqual(['cand_b'])
    expect(o.bestScore.t1).toBe(1.0)
    expect(o.ownershipCount).toEqual({ cand_a: 1, cand_b: 1 })
  })

  it('ties go to every candidate at the max score, sorted', () => {
    const cands = ownershipCandidates([
      node({ id: 'cand_b', per_task: { t1: 1.0 } }),
      node({ id: 'cand_a', per_task: { t1: 1.0 } }),
    ])
    const o = computeOwnership(cands)
    expect(o.owners.t1).toEqual(['cand_a', 'cand_b'])
    expect(o.ownershipCount).toEqual({ cand_a: 1, cand_b: 1 })
  })

  it('excludes candidates with no per_task from the ownership universe', () => {
    const cands = ownershipCandidates([
      node({ id: 'cand_a', per_task: { t1: 1.0 } }),
      node({ id: 'cand_screened_only', per_task: {} }),
    ])
    expect(cands.map((n) => n.id)).toEqual(['cand_a'])
  })
})
