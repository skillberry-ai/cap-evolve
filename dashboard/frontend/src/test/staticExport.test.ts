/**
 * The committed static export (`examples/tau2_airline/run_full/ui`) is a real run dir
 * with NO events.jsonl and a summary written before `capabilities` / `baseline_stderr`
 * existed. Every assertion here is about that lossy shape: the UI must fall back to the
 * data it does have instead of printing a blank tab or a false cause.
 */
import { describe, expect, it } from 'vitest'
import { gateRowsFromNodes } from '../components/GatePanel'
import { buildTabs } from '../routes/RunDeepDive'
import type { GraphNode, RunDetail } from '../lib/types'

const nodes: GraphNode[] = [
  { id: 'seed', parent: null, children: ['cand_0001'], status: 'seed', val: 0.536, iteration: 0 },
  {
    id: 'cand_0001',
    parent: 'seed',
    children: [],
    status: 'accepted',
    val: 0.582,
    iteration: 1,
    parent_val: 0.536,
    reason: 'paired Δ̄=+0.0460 > 0.2·SE',
    per_task: { '0': 1, '1': 0 },
  },
  {
    id: 'cand_0002',
    parent: 'cand_0001',
    children: [],
    status: 'rejected',
    val: 0.512,
    iteration: 2,
    parent_val: 0.582,
    reason: 'regression vs parent',
  },
]

const detail = (over: Partial<RunDetail['summary']> = {}): RunDetail =>
  ({
    run_id: 'run_full',
    path: '/tmp/run_full',
    graph: { nodes, root: 'seed', best_id: 'cand_0001' },
    summary: { baseline_val: 0.536, ...over },
  }) as unknown as RunDetail

describe('gateRowsFromNodes', () => {
  it('rebuilds the verdict rows a missing event stream took away', () => {
    const rows = gateRowsFromNodes(nodes)
    expect(rows.map((r) => r.candidate)).toEqual(['cand_0001', 'cand_0002'])
    expect(rows[0].verdict).toBe('accept')
    expect(rows[1].verdict).toBe('reject')
    expect(rows[0].delta).toBeCloseTo(0.046, 6)
    expect(rows[1].delta).toBeCloseTo(-0.07, 6)
    expect(rows[0].reason).toContain('paired')
  })

  it('reads SE, n and the bar out of the reason — and never the bar as the SE', () => {
    const [r] = gateRowsFromNodes([
      nodes[0],
      { ...nodes[1], reason: 'paired \u0394\u0304=+0.0460 > 0.2\u00b7SE=0.0062 (SE=0.0308, n=50)' },
    ])
    expect(r.stderr).toBe(0.0308) // the standalone SE, NOT the 0.2\u00b7SE bar
    expect(r.k_se).toBe(0.2)
    expect(r.threshold).toBe(0.0062)
    expect(r.n).toBe(50)
    expect(r.delta).toBe(0.046)
  })

  it('leaves a statistic the reason never carried empty rather than inventing it', () => {
    const [r] = gateRowsFromNodes([nodes[0], { ...nodes[1], reason: 'accepted' }])
    expect(r.stderr).toBeNull()
    expect(r.n).toBeNull()
    expect(r.threshold).toBeNull()
  })

  it('never emits a row for the seed — it was never gated', () => {
    expect(gateRowsFromNodes(nodes).some((r) => r.candidate === 'seed')).toBe(false)
  })
})

describe('buildTabs', () => {
  it('infers Tasks and Diffs from the payload when capabilities are absent', () => {
    const labels = buildTabs(undefined, detail({ git_log: [{ hash: 'abc', subject: 's' }] })).map(
      (t) => t.label,
    )
    expect(labels).toContain('Tasks')
    expect(labels).toContain('Diffs')
    // Never inferred: rollouts sit behind an endpoint this page cannot probe.
    expect(labels).not.toContain('Trajectories')
  })

  it('still omits a tab the payload has no data for', () => {
    const labels = buildTabs(undefined, detail()).map((t) => t.label)
    expect(labels).not.toContain('Diffs')
    expect(labels).toEqual(['Overview', 'Candidates', 'Gate', 'Tasks', 'Cost', 'Logs', 'Memory', 'Files'])
  })

  it('an explicit capabilities map still wins over inference', () => {
    const labels = buildTabs(
      { per_task: false, diffs: false } as never,
      detail({ git_log: [{ hash: 'abc', subject: 's' }] }),
    ).map((t) => t.label)
    expect(labels).not.toContain('Tasks')
    expect(labels).not.toContain('Diffs')
  })
})
