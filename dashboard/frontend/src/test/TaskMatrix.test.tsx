/**
 * The Tasks tab must show only what the SELECTED candidate actually touched, not the
 * full task universe padded with tasks it never ran (subset selection is fully
 * agent-controlled — PR #469/#473).
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TaskMatrix } from '../components/TaskMatrix'
import type { GraphNode, RunSummaryDetail } from '../lib/types'

const summary = (over: Partial<RunSummaryDetail> = {}): RunSummaryDetail =>
  ({
    run_id: 'run_x',
    algorithm: 'agent-optimize',
    status: 'accepted',
    baseline_val: 0.5,
    best_val: 0.6,
    delta_pct: null,
    test_reward: null,
    counts: { accepted: 1, rejected: 0, indecisive: 0, failed: 0, seed: 1, total: 2 },
    tasks: ['t1', 't2', 't3'],
    ...over,
  }) as RunSummaryDetail

const node = (over: Partial<GraphNode> = {}): GraphNode =>
  ({ id: 'cand_a', parent: 'seed', children: [], status: 'accepted', val: 0.6, ...over }) as GraphNode

const seed = node({ id: 'seed', status: 'seed', val: 0.5, per_task: { t1: 1, t2: 0, t3: 1 } })
const subsetCandidate = node({ id: 'cand_subset', per_task: { t2: 1 } })
const fullCandidate = node({ id: 'cand_full', per_task: { t1: 1, t2: 1, t3: 0 } })

describe('TaskMatrix', () => {
  it('shows the full task universe when no candidate is selected', () => {
    render(<TaskMatrix summary={summary()} nodes={[seed, subsetCandidate, fullCandidate]} />)
    expect(screen.getByText('t1')).toBeInTheDocument()
    expect(screen.getByText('t2')).toBeInTheDocument()
    expect(screen.getByText('t3')).toBeInTheDocument()
  })

  it('narrows to exactly the subset a screened candidate was evaluated on', () => {
    render(
      <TaskMatrix
        summary={summary()}
        nodes={[seed, subsetCandidate, fullCandidate]}
        selectedId="cand_subset"
      />,
    )
    expect(screen.getByText('t2')).toBeInTheDocument()
    expect(screen.queryByText('t1')).not.toBeInTheDocument()
    expect(screen.queryByText('t3')).not.toBeInTheDocument()
    expect(screen.getAllByText(/cand_subset/).length).toBeGreaterThan(0)
  })

  it('shows the full set for a candidate evaluated on every task', () => {
    render(
      <TaskMatrix
        summary={summary()}
        nodes={[seed, subsetCandidate, fullCandidate]}
        selectedId="cand_full"
      />,
    )
    expect(screen.getByText('t1')).toBeInTheDocument()
    expect(screen.getByText('t2')).toBeInTheDocument()
    expect(screen.getByText('t3')).toBeInTheDocument()
  })
})
