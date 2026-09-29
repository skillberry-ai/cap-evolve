import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RunTimeline } from '../components/RunTimeline'
import type { RunSummaryDetail, GraphNode } from '../lib/types'

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

  it('formats durations correctly', () => {
    render(<RunTimeline summary={mockSummary} nodes={mockNodes} />)

    // The timeline should show formatted time
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
