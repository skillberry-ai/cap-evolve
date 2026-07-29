import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RunDeepDive } from '../routes/RunDeepDive'
import { LivePendingError } from '../lib/api'

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return { ...actual, api: { ...actual.api, run: vi.fn() } }
})

afterEach(() => vi.restoreAllMocks())

function renderRunDeepDive() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/runs/run_suite']}>
        <Routes>
          <Route path="/runs/:id" element={<RunDeepDive />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RunDeepDive error states', () => {
  it('shows a friendly pending message for a live run with no snapshot yet, instead of a raw 404', async () => {
    const { api } = await import('../lib/api')
    vi.mocked(api.run).mockRejectedValue(new LivePendingError('404 Not Found for data/runs_run_suite.json'))
    renderRunDeepDive()
    expect(await screen.findByText(/Hold on/)).toBeInTheDocument()
    expect(screen.queryByText(/Couldn.t load run/)).not.toBeInTheDocument()
  })

  it(
    'shows the generic error message for a real (non-live-pending) failure',
    async () => {
      const { api } = await import('../lib/api')
      vi.mocked(api.run).mockRejectedValue(new Error('500 Internal Server Error for /api/runs/run_suite'))
      renderRunDeepDive()
      await waitFor(() => expect(screen.getByText(/Couldn.t load run/)).toBeInTheDocument(), { timeout: 10_000 })
      expect(screen.queryByText(/Hold on/)).not.toBeInTheDocument()
    },
    15_000,
  )
})
