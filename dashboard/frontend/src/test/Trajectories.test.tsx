import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Trajectories } from '../components/Trajectories'
import type { RolloutRow } from '../lib/types'

const ROWS: RolloutRow[] = [
  { task_id: 't1', candidate: 'cand_0001', trial: 0, split: 'val', reward: 1, feedback: 'correct', file: 't1__cand_0001__t0.json' },
  { task_id: 't2', candidate: 'cand_0001', trial: 0, split: 'val', reward: 0, feedback: 'wrong', file: 't2__cand_0001__t0.json' },
]

afterEach(() => vi.restoreAllMocks())

describe('Trajectories', () => {
  it('lists rollouts worst-first', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(ROWS), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <Trajectories runId="run_demo" />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('t2')).toBeInTheDocument() // worst (reward 0) renders
    const rowOrder = screen.getAllByText(/^t[12]$/).map((el) => el.textContent)
    expect(rowOrder[0]).toBe('t2') // sorted ascending by reward
  })
})
