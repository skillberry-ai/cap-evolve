import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Hub } from '../routes/Hub'
import type { RunSummary } from '../lib/types'

const RUN: RunSummary = {
  run_id: 'run_demo',
  path: '/x/run_demo',
  algorithm: 'hill-climb',
  status: 'done',
  best_val: 1.0,
  baseline_val: 0.0,
  delta_pct: 100,
  iterations: 3,
  total_usd: 0.12,
  mtime: 1,
}

function renderHub() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Hub />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('Hub', () => {
  it('renders a run row from the API', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([RUN]), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    renderHub()
    expect(await screen.findByText('run_demo')).toBeInTheDocument()
    expect(screen.getByText('hill-climb')).toBeInTheDocument()
    expect(screen.getByText('100.0%')).toBeInTheDocument() // best
    expect(screen.getByText('+100.0%')).toBeInTheDocument() // delta
  })

  it('shows an empty state when there are no runs', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    renderHub()
    await waitFor(() => expect(screen.getByText('No runs yet')).toBeInTheDocument())
  })
})
