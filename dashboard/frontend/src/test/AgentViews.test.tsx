/**
 * Panels that used to render a header with nothing under it, or a confident zero where
 * no measurement exists. Each case below shipped as a visible defect on a real run.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { FreeformPanel, ScreensPanel } from '../components/AlgoPanels'
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

describe('FreeformPanel', () => {
  it('explains the awaiting-agent state instead of rendering an empty table header', () => {
    render(<FreeformPanel summary={summary()} nodes={[node({ id: 'seed', status: 'seed' })]} />)
    expect(screen.getByText(/No candidate has been committed yet/)).toBeInTheDocument()
    expect(screen.queryByText(/Round log/)).not.toBeInTheDocument()
  })

  it('shows which tasks each commit fixed and broke', () => {
    render(
      <FreeformPanel
        summary={summary({ splits: { train: 4, val: 2, test: 2, seed: 0, no_holdout: false, warning: '' } })}
        nodes={[node({ reason: 'churn', fixed: ['t2'], broke: ['t1'] })]}
      />,
    )
    expect(screen.getByText('fixed t2')).toBeInTheDocument()
    expect(screen.getByText('broke t1')).toBeInTheDocument()
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

describe('ScreensPanel', () => {
  const screenRow = (over: Partial<ScreenRow> = {}): ScreenRow =>
    ({
      candidate: 'cand_a', screen_tag: 'cand_a__screen1', tier: 1, decision: 'promote',
      inconclusive: true, mean_delta: 0.5, se: 0.5, n: 2, threshold: -0.5,
      net_rollouts: -2, ids: ['t1', 't2'], holdout: ['t1'], informative: ['t2'],
      fixed: ['t2'], regressed: ['t1'], pool_n: 2, t: 1, ...over,
    })

  // The footer legend also contains the "≠ screen" glyph, so assert inside the row.
  const flagsInRow = (container: HTMLElement) =>
    [...container.querySelectorAll('tbody span')].some((e) => e.textContent === '≠ screen')

  it('flags a screen whose promotion the full val eval did not reproduce', () => {
    const { container } = render(
      <ScreensPanel screens={[screenRow()]} nodes={[node({ status: 'rejected', val: 0.5 })]} />,
    )
    expect(screen.getByText('promote · inconclusive')).toBeInTheDocument()
    expect(flagsInRow(container)).toBe(true)
    expect(screen.getByText(/holdout t1/)).toBeInTheDocument()
  })

  it('does not claim a disagreement for a candidate that never reached a full val eval', () => {
    const { container } = render(<ScreensPanel screens={[screenRow()]} nodes={[]} />)
    expect(flagsInRow(container)).toBe(false)
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
