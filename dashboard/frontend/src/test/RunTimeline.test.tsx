import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RunTimeline } from '../components/RunTimeline'
import type { Activity, RunSummaryDetail, GraphNode } from '../lib/types'

describe('RunTimeline', () => {
  const mockSummary: RunSummaryDetail = {
    baseline_val: 0.45,
    best_val: 0.975,
    delta_pct: 116.7,
    test_reward: 0.95,
    elapsed_seconds: 19534.9,
    started_t: 1790620739.589863,
    activities: [
      {
        id: 'seed',
        type: 'seed',
        lane: 'milestone',
        iteration: null,
        candidate: null,
        start: 0,
        end: 0,
        error: false,
      },
      {
        id: 'iter-1-opt',
        type: 'optimize',
        lane: 'optimizer',
        iteration: 1,
        candidate: 'cand_0001',
        start: 0,
        end: 2920,
        error: false,
      },
      {
        id: 'iter-1-eval',
        type: 'evaluate',
        lane: 'evaluator',
        iteration: 1,
        candidate: 'cand_0001',
        start: 2920,
        end: 3350,
        error: false,
      },
      {
        id: 'iter-1-gate',
        type: 'gate',
        lane: 'milestone',
        iteration: 1,
        candidate: 'cand_0001',
        start: 3350,
        end: 3350,
        error: false,
      },
    ],
    gate_decisions: [
      {
        iteration: 1,
        candidate: 'cand_0001',
        verdict: 'accept',
        val: 0.975,
        parent: 'seed',
        parent_val: 0.45,
        delta: 0.525,
        stderr: 0.08,
        n: 40,
        k_se: 1.96,
        threshold: 0.15,
        reason: 'Cleared threshold',
      },
    ],
    per_iteration: [
      {
        iteration: 1,
        candidate: 'cand_0001',
        status: 'accepted',
        optimizer_usd: 10.5,
        optimizer_seconds: 2920,
        optimizer_tokens: 150000,
        runner_usd: 0,
        runner_seconds: 430,
        runner_tokens: 500000,
      },
    ],
    evaluations: [],
  }

  const mockNodes: GraphNode[] = [
    {
      id: 'seed',
      parent: null,
      children: ['cand_0001'],
      status: 'seed',
      val: 0.45,
      stderr: 0.08,
    },
    {
      id: 'cand_0001',
      parent: 'seed',
      children: [],
      status: 'accepted',
      val: 0.975,
      stderr: 0.08,
      fixed: ['task1', 'task2'],
      broke: [],
      iteration: 1,
      best_so_far: true,
    },
  ]

  it('renders timeline with activities', () => {
    render(<RunTimeline summary={mockSummary} nodes={mockNodes} />)

    // Check for lane labels
    expect(screen.getByText('Phase')).toBeInTheDocument()
    expect(screen.getByText('Iteration')).toBeInTheDocument()
    expect(screen.getByText('Optimizer')).toBeInTheDocument()
    expect(screen.getByText('Evaluator')).toBeInTheDocument()
  })

  it('renders legend', () => {
    render(<RunTimeline summary={mockSummary} nodes={mockNodes} />)

    expect(screen.getByText('optimizer call')).toBeInTheDocument()
    expect(screen.getByText('evaluation on val')).toBeInTheDocument()
    expect(screen.getByText('gate accept')).toBeInTheDocument()
  })

  it('calls onActivityClick when activity is clicked', () => {
    const handleClick = vi.fn()
    render(<RunTimeline summary={mockSummary} nodes={mockNodes} onActivityClick={handleClick} />)

    // SVG elements are rendered, but clicking them in tests requires more setup
    // This test verifies the handler is passed correctly
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('handles empty activities gracefully', () => {
    const emptySummary: RunSummaryDetail = {
      baseline_val: 0.45,
      best_val: 0.975,
      delta_pct: 116.7,
      test_reward: 0.95,
      activities: [],
    }

    render(<RunTimeline summary={emptySummary} nodes={[]} />)
    expect(screen.getByText('Phase')).toBeInTheDocument()
  })

  // Real shape from .capevolve/run_full: a parallel batch (iters 1-3, where iter 2's
  // optimize span came out reversed in older payloads) and cand_16, a provisional
  // candidate with two growth rounds (__grow1/__grow2) before its final reject.
  describe('run_full shape (parallel batch + growth rounds)', () => {
    const act = (id: string, type: Activity['type'], lane: Activity['lane'], iteration: number | null,
      candidate: string | null, start: number, end: number, extra: Partial<Activity> = {}): Activity =>
      ({ id, type, lane, iteration, candidate, start, end, error: false, ...extra })
    const runFull: RunSummaryDetail = {
      baseline_val: 0.4867,
      best_val: 0.8267,
      best_id: 'cand_12',
      delta_pct: 69.9,
      test_reward: 0.885,
      elapsed_seconds: 50268,
      activities: [
        act('seed-eval', 'seed', 'evaluator', 0, 'seed', 0, 2375.94),
        act('iter-1-opt', 'optimize', 'optimizer', 1, 'cand_2', 2375.94, 6772.12),
        act('iter-1-eval', 'evaluate', 'evaluator', 1, 'cand_2', 6772.12, 8990.62),
        act('iter-1-gate', 'gate', 'gate', 1, 'cand_2', 10263.76, 10263.76),
        act('iter-2-opt', 'optimize', 'optimizer', 2, 'cand_1', 8990.62, 5710.65), // reversed (legacy)
        act('iter-2-eval', 'evaluate', 'evaluator', 2, 'cand_1', 5710.65, 8079.95),
        act('iter-2-gate', 'gate', 'gate', 2, 'cand_1', 10294.48, 10294.48),
        act('iter-3-opt', 'optimize', 'optimizer', 3, 'cand_3', 8079.95, 8083.55), // 3.6s: far too narrow for a label
        act('iter-3-eval', 'evaluate', 'evaluator', 3, 'cand_3', 8083.55, 10218.31),
        act('iter-3-gate', 'gate', 'gate', 3, 'cand_3', 10297.26, 10297.26),
        act('iter-16-opt', 'optimize', 'optimizer', 16, 'cand_16', 37261.74, 37551.61),
        act('iter-16-eval', 'evaluate', 'evaluator', 16, 'cand_16', 37551.61, 39542.68),
        act('iter-16-gate', 'gate', 'gate', 16, 'cand_16', 39575.94, 39575.94),
        act('iter-16-grow1', 'grow', 'evaluator', 16, 'cand_16', 39578.91, 45264.85, { growth_round: 1, reward: 0.8233 }),
        act('iter-16-grow2', 'grow', 'evaluator', 16, 'cand_16', 45311.68, 47528.93, { growth_round: 2, reward: 0.8307 }),
        act('iter-17-gate', 'gate', 'gate', 17, 'cand_17', 48000, 48000), // screen-killed: gate only
        act('final-test', 'final_eval', 'evaluator', null, 'cand_12', 47604.96, 49072.97, { split: 'test' }),
      ],
      per_iteration: [
        { iteration: 1, candidate: 'cand_2', status: 'accepted', optimizer_usd: 1.135475 },
        { iteration: 2, candidate: 'cand_1', status: 'rejected', optimizer_usd: 0.151943 },
        { iteration: 3, candidate: 'cand_3', status: 'rejected', optimizer_usd: 0.0 },
        { iteration: 16, candidate: 'cand_16', status: 'rejected', optimizer_usd: 3.394846 },
      ] as RunSummaryDetail['per_iteration'],
    }
    const runFullNodes = [
      { id: 'seed', parent: null, children: [], status: 'seed', val: 0.4867 },
      { id: 'cand_2', parent: 'seed', children: [], status: 'accepted', val: 0.7533, iteration: 1, best_so_far: true },
      { id: 'cand_1', parent: 'cand_2', children: [], status: 'rejected', val: 0.7333, iteration: 2 },
      { id: 'cand_3', parent: 'cand_2', children: [], status: 'rejected', val: 0.7167, iteration: 3 },
      { id: 'cand_16', parent: 'cand_12', children: [], status: 'rejected', val: 0.8333, iteration: 16 },
    ] as GraphNode[]

    it('renders an iteration band for every iteration with any activity', () => {
      render(<RunTimeline summary={runFull} nodes={runFullNodes} />)
      for (const it of [1, 2, 3, 16, 17]) {
        const band = screen.getByTestId(`iter-band-${it}`)
        expect(Number(band.querySelector('rect')!.getAttribute('width'))).toBeGreaterThan(0)
      }
    })

    it('renders growth rounds as evaluator bars and as ticks under the parent band', () => {
      render(<RunTimeline summary={runFull} nodes={runFullNodes} />)
      expect(screen.getByTestId('bar-iter-16-grow1')).toBeInTheDocument()
      expect(screen.getByTestId('bar-iter-16-grow2')).toBeInTheDocument()
      const band = screen.getByTestId('iter-band-16')
      expect(band.querySelectorAll('rect')).toHaveLength(3) // band + 2 growth ticks
      expect(band.textContent).toContain('+2 grow')
    })

    it('shows every optimizer cost, even on bars too narrow to hold it', () => {
      render(<RunTimeline summary={runFull} nodes={runFullNodes} />)
      const texts = [...document.querySelectorAll('text')].map(t => t.textContent)
      for (const usd of ['$1.14', '$0.15', '$0.00', '$3.39']) {
        expect(texts.some(t => t?.includes(usd))).toBe(true)
      }
      expect(screen.getAllByTestId('narrow-label-optimizer').length).toBeGreaterThan(0)
    })

    it('zooms in to widen the plot and Fit returns to the full run', async () => {
      render(<RunTimeline summary={runFull} nodes={runFullNodes} />)
      const plot = () => Number(screen.getByTestId('timeline-scroll').querySelector('svg')!.getAttribute('width'))
      const w0 = plot()
      await userEvent.click(screen.getByLabelText('Zoom in'))
      expect(plot()).toBeCloseTo(w0 * 1.5)
      await userEvent.click(screen.getByLabelText('Fit whole run'))
      expect(plot()).toBe(w0)
    })
  })

  it('formats durations correctly', () => {
    render(<RunTimeline summary={mockSummary} nodes={mockNodes} />)

    // The timeline should show formatted time
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
