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

  it('renders the exact reward as visible cell text, not just a colour glyph', () => {
    render(<TaskMatrix summary={summary()} nodes={[seed, fullCandidate]} />)
    // fullCandidate: t1=1, t2=1, t3=0 -> "1.00" appears (twice: t1, t2) and "0.00" (t3).
    expect(screen.getAllByText('1.00').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.00').length).toBeGreaterThan(0)
  })

  it('marks a cell whose task the candidate fixed or broke vs its parent', () => {
    const withMovement = node({
      id: 'cand_move',
      per_task: { t1: 1, t2: 0, t3: 1 },
      fixed: ['t1'],
      broke: ['t2'],
    })
    render(<TaskMatrix summary={summary()} nodes={[seed, withMovement]} />)
    expect(screen.getByLabelText(/t1 on cand_move:.*fixed vs parent/)).toBeInTheDocument()
    expect(screen.getByLabelText(/t2 on cand_move:.*broke vs parent/)).toBeInTheDocument()
  })

  it("renders a real (non-screen) candidate's own reason text", () => {
    const rejected = node({ id: 'cand_r', per_task: { t1: 0 }, reason: 'churn — no net gain' })
    render(<TaskMatrix summary={summary()} nodes={[seed, rejected]} />)
    expect(screen.getByText('churn — no net gain')).toBeInTheDocument()
  })

  it('groups candidates gated by the same round.py invocation under one round_id', () => {
    const a = node({ id: 'cand_a', per_task: { t1: 1 }, round_id: 'round_i1' })
    const b = node({ id: 'cand_b', per_task: { t1: 0 }, round_id: 'round_i1' })
    const c = node({ id: 'cand_c', per_task: { t1: 1 }, round_id: 'round_i2' })
    render(<TaskMatrix summary={summary()} nodes={[seed, a, b, c]} />)
    // The round band header carries the batch id as a title/tooltip on the spanning cell.
    expect(screen.getByTitle(/gated together by round.py: round_i1/)).toBeInTheDocument()
    expect(screen.getByTitle(/gated together by round.py: round_i2/)).toBeInTheDocument()
  })
})
