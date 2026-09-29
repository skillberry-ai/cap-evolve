import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OptimizerStory } from '../components/OptimizerStory'
import type { GraphNode, GateDecision, PerIterationCost } from '../lib/types'

describe('OptimizerStory', () => {
  const mockNodes: GraphNode[] = [
    {
      id: 'seed',
      parent: null,
      children: ['cand_0001'],
      status: 'seed',
      val: 0.45,
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
      diagnosis: {
        candidate: 'cand_0001',
        headline: 'Fix formula handling',
        clusters: [{ id: 'A', name: 'Test', detail: '', tasks: [], scope: '', latent: false, tag: '' }],
        edits: [{ id: 'E1', title: 'Edit 1', files: [], lever: '', clusters: [], blast_radius: '', verified: '' }],
        skipped: [],
        techniques: [],
      },
    },
    {
      id: 'cand_0002',
      parent: 'cand_0001',
      children: [],
      status: 'rejected',
      val: 0.95,
      stderr: 0.08,
      fixed: ['task3'],
      broke: ['task1'],
      iteration: 2,
    },
  ]

  const mockGates: GateDecision[] = [
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
    {
      iteration: 2,
      candidate: 'cand_0002',
      verdict: 'reject',
      val: 0.95,
      parent: 'cand_0001',
      parent_val: 0.975,
      delta: -0.025,
      stderr: 0.08,
      n: 40,
      k_se: 1.96,
      threshold: 0.15,
      reason: 'Below threshold',
    },
  ]

  const mockPerIteration: PerIterationCost[] = [
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
    {
      iteration: 2,
      candidate: 'cand_0002',
      status: 'rejected',
      optimizer_usd: 8.2,
      optimizer_seconds: 2100,
      optimizer_tokens: 120000,
      runner_usd: 0,
      runner_seconds: 450,
      runner_tokens: 520000,
    },
  ]

  it('renders table with iteration rows', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('Iteration')).toBeInTheDocument()
    expect(screen.getByText('Candidate')).toBeInTheDocument()
    expect(screen.getByText('Diagnosis Summary')).toBeInTheDocument()
    expect(screen.getByText('Outcome')).toBeInTheDocument()
  })

  it('displays iteration numbers', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows candidate IDs with status badges', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('cand_0001')).toBeInTheDocument()
    expect(screen.getByText('cand_0002')).toBeInTheDocument()
    
    // Check for status indicators
    const acceptBadges = screen.getAllByText('✓')
    const rejectBadges = screen.getAllByText('✕')
    expect(acceptBadges.length).toBeGreaterThan(0)
    expect(rejectBadges.length).toBeGreaterThan(0)
  })

  it('displays diagnosis headlines', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText(/Fix formula handling/)).toBeInTheDocument()
    expect(screen.getByText(/1 clusters, 1 edits/)).toBeInTheDocument()
  })

  it('shows fixed and broke counts', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('+2')).toBeInTheDocument() // cand_0001 fixed 2
    expect(screen.getByText('+1')).toBeInTheDocument() // cand_0002 fixed 1
    expect(screen.getByText('-1')).toBeInTheDocument() // cand_0002 broke 1
  })

  it('displays time and cost metrics', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('$10.50')).toBeInTheDocument()
    expect(screen.getByText('$8.20')).toBeInTheDocument()
  })

  it('calls onIterationClick when row is clicked', () => {
    const handleClick = vi.fn()
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
        onIterationClick={handleClick}
      />
    )

    const rows = screen.getAllByRole('row')
    // Click the first data row (skip header)
    if (rows[1]) {
      rows[1].click()
      expect(handleClick).toHaveBeenCalledWith(1)
    }
  })

  it('handles empty nodes gracefully', () => {
    render(
      <OptimizerStory
        nodes={[]}
        gates={[]}
        perIteration={[]}
      />
    )

    expect(screen.getByText('No iterations found')).toBeInTheDocument()
  })

  it('shows "No diagnosis" for nodes without diagnosis', () => {
    render(
      <OptimizerStory
        nodes={mockNodes}
        gates={mockGates}
        perIteration={mockPerIteration}
      />
    )

    expect(screen.getByText('No diagnosis')).toBeInTheDocument()
  })
})
