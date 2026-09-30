import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IterationDetail } from '../components/IterationDetail'
import fixtureData from './fixtures/run_payload.json'
import type { GraphNode, GateDecision } from '../lib/types'

describe('IterationDetail', () => {
  const runId = fixtureData.summary.run_id
  const nodes = fixtureData.graph.nodes as GraphNode[]
  const candidate = nodes.find(n => n.id === 'cand_0001')!
  const parent = nodes.find(n => n.id === 'seed')!
  const gate: GateDecision = {
    iteration: 1,
    candidate: 'cand_0001',
    verdict: 'accept',
    val: 0.75,
    parent: 'seed',
    parent_val: 0.5,
    delta: 0.25,
    stderr: 0.0,
    n: 4,
    k_se: 1.96,
    threshold: 0.0,
    reason: 'up'
  }

  it('renders overview tab without crashing', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Iteration 1')).toBeTruthy()
    expect(screen.getAllByText('cand_0001').length).toBeGreaterThan(0)
  })

  it('renders diagnosis tab with diagnosis data', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    // Tab should be present
    expect(screen.getByText('Optimizer · diagnosis')).toBeTruthy()
  })

  it('renders diagnosis tab fallback when no diagnosis', () => {
    const onClose = vi.fn()
    const candidateNoDiagnosis = { ...candidate, diagnosis: undefined }
    render(
      <IterationDetail
        iteration={1}
        candidate={candidateNoDiagnosis}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    // Tab should still be present
    expect(screen.getByText('Optimizer · diagnosis')).toBeTruthy()
  })

  it('renders gate tab when gate data exists', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Gate decision')).toBeTruthy()
  })

  it('renders diff tab when parent exists', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    expect(screen.getByText('Changes (diff)')).toBeTruthy()
  })

  it('renders PROCESS.md tab', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    expect(screen.getByText('PROCESS.md')).toBeTruthy()
  })

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn()
    render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    const closeButton = screen.getByText('Close')
    closeButton.click()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders verdict badge with text and without custom bg class', () => {
    const onClose = vi.fn()
    const { container } = render(
      <IterationDetail
        iteration={1}
        candidate={candidate}
        parent={parent}
        gate={gate}
        runId={runId}
        onClose={onClose}
      />
    )
    
    // Should render "accept" text
    expect(screen.getByText('accept')).toBeTruthy()
    
    // Should not use custom bg-[var(--accepted)] class
    const badges = container.querySelectorAll('[class*="bg-[var(--accepted)]"]')
    expect(badges.length).toBe(0)
  })
})
