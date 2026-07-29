import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CostPanel } from '../components/CostPanel'
import { FileTree } from '../components/FileTree'
import { GitDiff } from '../components/GitDiff'
import type { RunSummaryDetail } from '../lib/types'

afterEach(() => vi.restoreAllMocks())

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>)
}

/** Route fetch by URL so a component making several calls gets the right payload. */
function mockFetchByUrl(routes: Array<[RegExp, unknown]>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input)
    const hit = routes.find(([re]) => re.test(url))
    const body = hit ? hit[1] : {}
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

describe('CostPanel', () => {
  it('shows per-role cost and a budget meter that flags warnings', () => {
    const summary = {
      cost: { intake_usd: 0.1, optimizer_usd: 2.0, runner_usd: 1.0, total_usd: 3.1 },
      tokens_by_role: { runner: 5000, optimizer: 1200, intake: 100 },
      optimizer_seconds: 12, runner_seconds: 30, intake_seconds: 4,
      budget: { max_usd: 4 },
      spent: { metric_calls: 10 },
      budget_warnings: [{ metric: 'max_usd', pct: 50, spent: 3.1, limit: 4 }],
    } as unknown as RunSummaryDetail
    wrap(<CostPanel summary={summary} />)
    expect(screen.getByText('Cost by role')).toBeInTheDocument()
    expect(screen.getByText('Optimizer')).toBeInTheDocument()
    expect(screen.getByText('Total spend')).toBeInTheDocument()
    expect(screen.getByText(/crossed 50%/)).toBeInTheDocument()
  })

  // Model tiering (#132): the aux tier is part of total_usd, so the per-role tiles must
  // add up to the total printed above them. Before aux became a role the tiles summed
  // to 0.61 against a header total of 0.81 — a visible arithmetic gap.
  it('per-role costs sum to the stated total on a TIERED run (aux included)', () => {
    const summary = {
      cost: { intake_usd: 0.01, optimizer_usd: 0.5, runner_usd: 0.1, aux_usd: 0.2, total_usd: 0.81 },
      tokens_by_role: { runner: 5000, optimizer: 1200, intake: 100, aux: 400 },
      optimizer_seconds: 12, runner_seconds: 30, intake_seconds: 4,
    } as unknown as RunSummaryDetail
    wrap(<CostPanel summary={summary} />)
    expect(screen.getByText('Aux')).toBeInTheDocument()
    // read the RENDERED tile figures inside the "Cost by role" card, not the props
    const card = screen.getByText('Cost by role').closest('.p-4')!
    const tiles = [...card.querySelectorAll('.grid > div')]
    const shown = tiles.map((t) => ({
      label: t.querySelector('.uppercase')!.textContent!.trim(),
      usd: Number(t.querySelector('.font-semibold')!.textContent!.replace('$', '')),
    }))
    expect(shown.map((s) => s.label)).toEqual(['Intake', 'Optimizer', 'Runner', 'Aux'])
    expect(shown.map((s) => s.usd)).toEqual([0.01, 0.5, 0.1, 0.2])
    const sum = shown.reduce((a, s) => a + s.usd, 0)
    expect(sum).toBeCloseTo(0.81, 6)   // == the header total, printed as $0.810
    expect(card.querySelector('.text-accent')!.textContent).toBe(`$${sum.toFixed(3)}`)
  })

  it('hides the Aux role entirely when nothing was spent on the cheap tier', () => {
    const summary = {
      cost: { intake_usd: 0.1, optimizer_usd: 2.0, runner_usd: 1.0, aux_usd: 0, total_usd: 3.1 },
      tokens_by_role: { runner: 5000, optimizer: 1200, intake: 100, aux: 0 },
    } as unknown as RunSummaryDetail
    wrap(<CostPanel summary={summary} />)
    expect(screen.queryByText('Aux')).not.toBeInTheDocument()
  })
})

describe('FileTree', () => {
  it('lists the run directory (memory dir first)', async () => {
    mockFetchByUrl([
      [/\/tree/, { path: '', entries: [{ name: 'memory', path: 'memory', type: 'dir', children: [
        { name: 'notes.md', path: 'memory/notes.md', type: 'file', size: 20 },
      ] }] }],
    ])
    wrap(<FileTree runId="run_demo" />)
    expect(await screen.findByText('memory')).toBeInTheDocument()
  })
})

describe('GitDiff', () => {
  it('lists iteration commits from the store', async () => {
    mockFetchByUrl([
      [/\/git\/log/, [
        { hash: 'aaa', subject: 'iter 1: seed', iter: 0 },
        { hash: 'bbb', subject: 'iter 2: ACCEPT cand', iter: 1 },
      ]],
      [/\/git\/diff/, { from: 'bbb~1', to: 'bbb', available: true, files: [
        { path: 'art.txt', added: 1, removed: 1, rows: [{ t: 'add', l: 'v2' }, { t: 'del', l: 'v1' }] },
      ] }],
    ])
    wrap(<GitDiff runId="run_demo" />)
    expect(await screen.findByText('iter 2: ACCEPT cand')).toBeInTheDocument()
  })
})
