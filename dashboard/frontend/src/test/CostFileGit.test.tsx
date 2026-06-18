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
