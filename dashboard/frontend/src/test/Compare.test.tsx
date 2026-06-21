import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Compare } from '../routes/Compare'
import type { CompareResult } from '../lib/types'

const PAYLOAD: CompareResult = {
  runs: [
    {
      run_id: 'run_a',
      algorithm: 'gepa',
      baseline_val: 0.2,
      best_val: 0.9,
      delta_pct: 70,
      test_reward: 0.85,
      total_usd: 0.5,
      tokens: 1000,
      iterations: 5,
      series: [
        { iteration: 0, best_so_far: 0.2 },
        { iteration: 1, best_so_far: 0.9 },
      ],
    },
  ],
  tasks: ['t1'],
}

afterEach(() => vi.restoreAllMocks())

describe('Compare', () => {
  it('renders the compare table from the API', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(PAYLOAD), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/compare?ids=run_a']}>
          <Compare />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    // Wait for data-dependent cells (run_a also appears in the subtitle pre-load).
    expect(await screen.findByText('gepa')).toBeInTheDocument()
    expect(screen.getByText('+70.0%')).toBeInTheDocument()
    expect(screen.getAllByText('run_a').length).toBeGreaterThan(0)
  })
})
