import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IterationDetail } from '../components/IterationDetail'
import type { GraphNode, GateDecision } from '../lib/types'

describe('IterationDetail', () => {
  const mockParent: GraphNode = {
    id: 'seed',
    parent: null,
    children: ['cand_0001'],
    status: 'seed',
    val: 0.45,
    stderr: 0.08,
  }

  const mockCandidate: GraphNode = {
    id: 'cand_0001',
    parent: 'seed',
    children: [],
    status: 'accepted',
    val: 0.975,
    stderr: 0.08,
    fixed: ['task1', 'task2'],
    broke: [],
    iteration: 1,
    optimizer_seconds: 2920,
    runner_seconds: 430,
    opt_cost_usd: 10.5,
    cost_usd: 10.5,
    opt_tokens: 150000,
    tokens: 650000,
  }

  const mockGate: GateDecision = {
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
  }

  const mockOnClose = vi.fn()

  it('renders iteration header', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('Iteration 1')).toBeInTheDocument()
    // Candidate ID appears multiple times (header badge and in overview)
    const candidateElements = screen.getAllByText(/cand_0001/)
    expect(candidateElements.length).toBeGreaterThan(0)
    expect(screen.getByText(/accepted/)).toBeInTheDocument()
  })

  it('displays parent to candidate delta', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText(/from seed/)).toBeInTheDocument()
    expect(screen.getByText(/45\.0%.*→.*97\.5%/)).toBeInTheDocument()
  })

  it('renders overview tab by default', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('Parent')).toBeInTheDocument()
    expect(screen.getByText('Optimizer')).toBeInTheDocument()
    expect(screen.getByText('Candidate')).toBeInTheDocument()
    expect(screen.getByText('Evaluation')).toBeInTheDocument()
    expect(screen.getByText('Gate')).toBeInTheDocument()
  })

  it('shows stats grid with fixed/broke counts', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('Fixed')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Broke')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    const closeButton = screen.getByText('Close')
    closeButton.click()
    expect(mockOnClose).toHaveBeenCalledTimes(1)
  })

  it('shows diagnosis tab when diagnosis exists', () => {
    const candidateWithDiagnosis: GraphNode = {
      ...mockCandidate,
      diagnosis: {
        candidate: 'cand_0001',
        headline: 'Test diagnosis',
        clusters: [],
        edits: [],
        skipped: [],
        techniques: [],
      },
    }

    render(
      <IterationDetail
        iteration={1}
        candidate={candidateWithDiagnosis}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('Optimizer · diagnosis')).toBeInTheDocument()
  })

  it('hides diagnosis tab when no diagnosis', () => {
    render(
      <IterationDetail
        iteration={1}
        candidate={mockCandidate}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.queryByText('Optimizer · diagnosis')).not.toBeInTheDocument()
  })

  it('shows prompt map tab when prompt_map exists', () => {
    const candidateWithPromptMap: GraphNode = {
      ...mockCandidate,
      prompt_map: {
        'prompt.md': {
          lines: 100,
          bytes: 5000,
          headings: [],
          add: [],
          rem: [],
          touched: [],
        },
      },
    }

    render(
      <IterationDetail
        iteration={1}
        candidate={candidateWithPromptMap}
        parent={mockParent}
        gate={mockGate}
        runId="run_123"
        onClose={mockOnClose}
      />
    )

    expect(screen.getByText('Prompt map')).toBeInTheDocument()
  })
})
