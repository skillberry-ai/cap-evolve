/**
 * Panels that used to render a header with nothing under it, or a confident zero where
 * no measurement exists. Each case below shipped as a visible defect on a real run.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RoundsTimeline } from '../components/AlgoPanels'
import { GatePanel } from '../components/GatePanel'
import { KpiStrip } from '../components/KpiStrip'
import { Compare } from '../routes/Compare'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { GateDecision, GraphNode, RunSummaryDetail, ScreenRow } from '../lib/types'

const summary = (over: Partial<RunSummaryDetail> = {}): RunSummaryDetail =>
  ({
    run_id: 'run_x',
    algorithm: 'agent-optimize',
    status: 'awaiting_agent',
    baseline_val: 0.5,
    best_val: 0.5,
    delta_pct: null,
    test_reward: null,
    counts: { accepted: 0, rejected: 0, indecisive: 0, failed: 0, seed: 1, total: 1 },
    ...over,
  }) as RunSummaryDetail

const node = (over: Partial<GraphNode> = {}): GraphNode =>
  ({ id: 'cand_a', parent: 'seed', children: [], status: 'rejected', val: 0.5, ...over }) as GraphNode

describe('RoundsTimeline', () => {
  it('explains the awaiting-agent state instead of rendering an empty round list', () => {
    render(
      <RoundsTimeline
        summary={summary()}
        nodes={[node({ id: 'seed', status: 'seed' })]}
        screens={[]}
      />,
    )
    expect(screen.getByText(/No candidate has been committed yet/)).toBeInTheDocument()
  })

  it('shows which tasks each commit fixed and broke', () => {
    render(
      <RoundsTimeline
        summary={summary({ splits: { train: 4, val: 2, test: 2, seed: 0, no_holdout: false, warning: '' } })}
        nodes={[node({ reason: 'churn', fixed: ['t2'], broke: ['t1'] })]}
        screens={[]}
      />,
    )
    expect(screen.getByText('fixed t2')).toBeInTheDocument()
    expect(screen.getByText('broke t1')).toBeInTheDocument()
  })

  it('surfaces an overridden gate — raw accept, control-relative reject, final reject', () => {
    render(
      <RoundsTimeline
        summary={summary({
          gate_decisions: [
            {
              iteration: 1, candidate: 'cand_a', verdict: 'reject', val: 0.45, parent: 'seed',
              parent_val: 0.43, delta: 0.02, stderr: 0.02, n: 30, k_se: 0.2, threshold: 0.01,
              reason: 'note', gate_verdict: 'accept', overrode_gate: true,
              reject_basis: 'driver_judgement', control_relative_verdict: 'reject',
              control_relative_delta: -0.01, verdict_stable: true, evidence_bar: 0.04,
            },
          ],
        })}
        nodes={[node({ id: 'cand_a', status: 'rejected', val: 0.45 })]}
        screens={[]}
      />,
    )
    expect(screen.getByText('overrode gate')).toBeInTheDocument()
    expect(screen.getByText('stable')).toBeInTheDocument()
    expect(screen.getByText('driver_judgement')).toBeInTheDocument()
  })

  it('flags a gate mean scored over a subset of the full val split', () => {
    render(
      <RoundsTimeline
        summary={summary({
          splits: { train: 4, val: 5, test: 2, seed: 0, no_holdout: false, warning: '' },
          gate_decisions: [
            {
              iteration: 1, candidate: 'cand_a', verdict: 'accept', val: 0.6, parent: 'seed',
              parent_val: 0.5, delta: 0.1, stderr: 0.02, n: 2, k_se: 0.2, threshold: 0.01,
              reason: '',
            },
          ],
        })}
        nodes={[node({ id: 'cand_a', status: 'accepted', val: 0.6 })]}
        screens={[]}
      />,
    )
    expect(screen.getByText('subset')).toBeInTheDocument()
  })

  it('does not flag a subset when the gate scored the whole val split', () => {
    render(
      <RoundsTimeline
        summary={summary({
          splits: { train: 4, val: 2, test: 2, seed: 0, no_holdout: false, warning: '' },
          gate_decisions: [
            {
              iteration: 1, candidate: 'cand_a', verdict: 'accept', val: 0.6, parent: 'seed',
              parent_val: 0.5, delta: 0.1, stderr: 0.02, n: 2, k_se: 0.2, threshold: 0.01,
              reason: '',
            },
          ],
        })}
        nodes={[node({ id: 'cand_a', status: 'accepted', val: 0.6 })]}
        screens={[]}
      />,
    )
    expect(screen.queryByText('subset')).not.toBeInTheDocument()
  })

  it('flags a round whose handover was not captured live', () => {
    render(
      <RoundsTimeline
        summary={summary()}
        nodes={[node({
          id: 'cand_a',
          context_warning: { what: 'JOURNAL.md', error: 'empty handover' },
        })]}
        screens={[]}
      />,
    )
    expect(screen.getByText(/NOT captured live/)).toBeInTheDocument()
  })
})

describe('RoundsTimeline screens', () => {
  const screenRow = (over: Partial<ScreenRow> = {}): ScreenRow =>
    ({
      candidate: 'cand_a', screen_tag: 'cand_a__screen1', tier: 1, decision: 'promote',
      inconclusive: true, mean_delta: 0.5, se: 0.5, n: 2, threshold: -0.5,
      net_rollouts: -2, ids: ['t1', 't2'], holdout: ['t1'], informative: ['t2'],
      fixed: ['t2'], regressed: ['t1'], pool_n: 2, t: 1, ...over,
    })

  it('shows the screen decision alongside its round', () => {
    render(
      <RoundsTimeline
        summary={summary()}
        nodes={[node({ id: 'cand_a', status: 'rejected', val: 0.5 })]}
        screens={[screenRow()]}
      />,
    )
    expect(screen.getByText('promote · inconclusive')).toBeInTheDocument()
  })

  it('flags a screen that predicted promote but whose candidate full val then rejected', () => {
    render(
      <RoundsTimeline
        summary={summary()}
        nodes={[node({ id: 'cand_a', status: 'rejected', val: 0.5 })]}
        screens={[screenRow({ mean_delta: 0.5, inconclusive: false })]}
      />,
    )
    expect(screen.getByText('≠ screen')).toBeInTheDocument()
  })

  it('does not flag a screen whose call agreed with the full-val verdict', () => {
    render(
      <RoundsTimeline
        summary={summary()}
        nodes={[node({ id: 'cand_a', status: 'accepted', val: 0.5 })]}
        screens={[screenRow({ mean_delta: 0.5, inconclusive: false })]}
      />,
    )
    expect(screen.queryByText('≠ screen')).not.toBeInTheDocument()
  })
})

describe('GatePanel', () => {
  const row = (over: Partial<GateDecision> = {}): GateDecision =>
    ({
      iteration: 1, candidate: 'cand_a', verdict: 'reject', val: 0.5, parent: 'seed',
      parent_val: 0.5, delta: null, stderr: null, n: null, k_se: null, threshold: null,
      reason: '', ...over,
    }) as GateDecision

  it('renders no rationale list when no decision recorded one', () => {
    // Previously this emitted one blank line per candidate — a column of bare ids.
    const { container } = render(<GatePanel summary={summary({ gate_decisions: [row()] })} />)
    expect(container.querySelectorAll('ul li')).toHaveLength(0)
  })

  it('renders the rationale a decision did record', () => {
    render(<GatePanel summary={summary({ gate_decisions: [row({ reason: 'churn — broke t1' })] })} />)
    expect(screen.getByText(/churn — broke t1/)).toBeInTheDocument()
  })
})

describe('KpiStrip', () => {
  it('says tokens are not recorded rather than showing a confident 0', () => {
    render(<KpiStrip summary={summary({ tokens: 0, tokens_by_role: { runner: 0, optimizer: 0, intake: 0 } })} />)
    // Scoped to the tokens fact: an unrecorded event_count says "not recorded" too.
    expect(
      screen.getByText('this runner does not report token counts').previousSibling,
    ).toHaveTextContent('not recorded')
  })

  it('says events are not recorded rather than "0 lines in events.jsonl"', () => {
    render(<KpiStrip summary={summary({ event_count: undefined })} />)
    expect(screen.getByText('this run dir ships no events.jsonl')).toBeInTheDocument()
    expect(screen.queryByText('lines in events.jsonl')).toBeNull()
  })

  it('reads the sealed test against the seed on the same split', () => {
    render(
      <KpiStrip
        summary={summary({ test_reward: 0.4167, test_baseline_reward: 0.4167, test_delta: 0, test_sealed: true })}
      />,
    )
    expect(screen.getByText(/seed 41\.7% · Δ \+?0\.000/)).toBeInTheDocument()
  })

  it('labels an unsealed test as not sealed yet instead of leaving a bare dash tile', () => {
    render(<KpiStrip summary={summary()} />)
    expect(screen.getByText('test — not sealed yet')).toBeInTheDocument()
  })

  it('does not blame a zero baseline when no baseline was measured at all', () => {
    // Live snapshot of run 33492876620: the baseline had not finished, so delta_pct was
    // null because there was NOTHING to divide — not because the baseline was 0.0. The
    // hint stated a reason the data does not support.
    render(<KpiStrip summary={summary({ baseline_val: null, best_val: null })} />)
    expect(screen.queryByText(/off a zero baseline/)).toBeNull()
    expect(screen.getByText(/no baseline measured yet/)).toBeInTheDocument()
  })

  it('still blames the zero baseline when the baseline really is 0', () => {
    render(<KpiStrip summary={summary({ baseline_val: 0, best_val: 0.4, delta_abs: 0.4 })} />)
    expect(screen.getByText(/off a zero baseline/)).toBeInTheDocument()
  })

  it('says spend was not reported rather than showing a confident $0.000', () => {
    // The real tau2 run made 68 rollouts through a proxy that reports no cost, so the
    // ledger sums to exactly $0. "$0.000" would assert a fact nobody measured.
    render(
      <KpiStrip
        summary={summary({
          cost: { optimizer_usd: 0, runner_usd: 0, intake_usd: 0, total_usd: 0, metered: false },
        })}
      />,
    )
    expect(screen.getByText('not reported')).toBeInTheDocument()
    expect(screen.queryByText('$0.000')).not.toBeInTheDocument()
  })

  it('still shows real dollars when the runner does report cost', () => {
    render(
      <KpiStrip
        summary={summary({
          cost: { optimizer_usd: 10, runner_usd: 2.98, intake_usd: 0, total_usd: 12.98, metered: true },
        })}
      />,
    )
    expect(screen.getByText('$12.98')).toBeInTheDocument()
    expect(screen.queryByText('not reported')).not.toBeInTheDocument()
  })
})

describe('Compare split guard', () => {
  it('warns when the selected runs were scored on different task sets', async () => {
    const qc = new QueryClient()
    const runs = [
      { run_id: 'run_toy', algorithm: 'hill-climb', baseline_val: 0, best_val: 1, delta_pct: null,
        test_reward: 1, total_usd: 0, tokens: 0, iterations: 3, tasks: ['a', 'b'], series: [] },
      { run_id: 'run_bench', algorithm: 'agent-optimize', baseline_val: 0.83, best_val: 0.83,
        delta_pct: 0, test_reward: 0.42, total_usd: 12.98, tokens: 0, iterations: 4,
        tasks: ['1', '2', '3'], series: [] },
    ]
    qc.setQueryData(['compare', ['run_toy', 'run_bench']], { runs, tasks: [] })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/compare?ids=run_toy,run_bench']}>
          <Compare />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/Different val splits/)).toBeInTheDocument()
    expect(screen.getByText(/run_toy: 2 tasks/)).toBeInTheDocument()
  })
})
