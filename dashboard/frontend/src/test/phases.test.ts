import { describe, expect, it } from 'vitest'
import { derivePhases } from '../lib/phases'
import type { RunDetail } from '../lib/types'

function detail(summary: Partial<RunDetail['summary']>): RunDetail {
  return {
    run_id: 'r',
    path: '/r',
    graph: { nodes: [], root: 'seed', best_id: null },
    summary: { baseline_val: null, best_val: null, delta_pct: null, test_reward: null, ...summary },
  }
}

const byKey = (d: RunDetail) => Object.fromEntries(derivePhases(d).map((p) => [p.key, p.status]))

describe('derivePhases', () => {
  it('marks finalize+report done when the test is sealed', () => {
    const s = byKey(
      detail({
        baseline_val: 0.2,
        best_val: 0.8,
        test_reward: 0.75,
        counts: { accepted: 1, rejected: 1, failed: 0, seed: 1, total: 3 },
      }),
    )
    expect(s.baseline).toBe('done')
    expect(s.algorithm).toBe('done')
    expect(s.finalize).toBe('done')
    expect(s.report).toBe('done')
  })

  it('shows algorithm active mid-run (baseline done, not finalized)', () => {
    const s = byKey(
      detail({
        baseline_val: 0.2,
        best_val: 0.5,
        counts: { accepted: 1, rejected: 0, failed: 0, seed: 1, total: 2 },
      }),
    )
    expect(s.baseline).toBe('done')
    expect(s.algorithm).toBe('active')
    expect(s.finalize).toBe('pending')
  })

  it('leaves later phases pending before a baseline exists', () => {
    const s = byKey(detail({}))
    expect(s.baseline).toBe('pending')
    expect(s.finalize).toBe('pending')
  })
})
