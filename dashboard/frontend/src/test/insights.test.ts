import { describe, expect, it } from 'vitest'
import { deadEnds, normalizeReason, toolUsage, whatHelped } from '../lib/insights'
import type { GraphNode, RolloutDetail } from '../lib/types'

function node(p: Partial<GraphNode> & { id: string }): GraphNode {
  return { parent: null, children: [], status: 'accepted', val: null, ...p }
}

describe('whatHelped', () => {
  it('ranks accepted candidates by improvement over parent', () => {
    const graph = {
      root: 'seed',
      best_id: 'c2',
      nodes: [
        node({ id: 'seed', status: 'seed', val: 0.2 }),
        node({ id: 'c1', parent: 'seed', val: 0.5 }),
        node({ id: 'c2', parent: 'c1', val: 0.9 }),
        node({ id: 'r1', parent: 'c2', status: 'rejected', val: 0.4 }),
      ],
    }
    const out = whatHelped(graph)
    expect(out.map((h) => h.id)).toEqual(['c2', 'c1']) // +0.4 then +0.3; rejected excluded
    expect(out[0].delta).toBeCloseTo(0.4)
  })
})

describe('normalizeReason + deadEnds', () => {
  it('collapses numeric noise so similar reasons group', () => {
    expect(normalizeReason('Δ=+0.0012 <= 1.0·SE=0.0003')).toBe(normalizeReason('Δ=+0.0099 <= 1.0·SE=0.0100'))
  })

  it('dedupes rejected reasons with counts', () => {
    const out = deadEnds([
      { candidate_id: 'a', summary: '', reason: 'Δ=+0.01 <= SE=0.02', val: 0 },
      { candidate_id: 'b', summary: '', reason: 'Δ=+0.03 <= SE=0.04', val: 0 },
      { candidate_id: 'c', summary: '', reason: 'broke correctness gate', val: 0 },
    ])
    expect(out[0].count).toBe(2) // the two numeric gate rejections collapse
    expect(out[0].examples).toEqual(['a', 'b'])
  })
})

describe('toolUsage', () => {
  it('aggregates tool-call frequency across rollouts', () => {
    const rollouts: RolloutDetail[] = [
      { rollout: { tool_calls: [{ name: 'search' }, { name: 'calc' }] } },
      { rollout: { tool_calls: [{ name: 'search' }] } },
      { rollout: {} },
    ]
    const out = toolUsage(rollouts)
    expect(out[0]).toEqual({ name: 'search', count: 2 })
    expect(out.find((t) => t.name === 'calc')?.count).toBe(1)
  })
})
