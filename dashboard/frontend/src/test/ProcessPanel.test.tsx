/**
 * The Process tab (issue #525). A static export has no /api/*, so the panel must read the
 * export's own `<slug>.html` file — relative to the data base, never an absolute /api/ path
 * that on Pages resolves outside the site. The live backend (a local `cap-evolve` run) must
 * keep loading the /api/* route directly.
 *
 * STATIC_MODE is read once at module load, so each test sets the window flag, resets the
 * module registry and imports fresh (react-query included, so the provider and the panel
 * share one instance).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

type WindowOverride = { __CAPEVOLVE_DATA_BASE__?: string; __CAPEVOLVE_STATIC__?: unknown }

const PAGE = '<!doctype html><html><body><h1>process snapshot</h1></body></html>'

beforeEach(() => vi.resetModules())

afterEach(() => {
  const w = window as unknown as WindowOverride
  delete w.__CAPEVOLVE_DATA_BASE__
  delete w.__CAPEVOLVE_STATIC__
  vi.unstubAllGlobals()
})

function stubFetch(respond: (url: string) => Response) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      return respond(url)
    }),
  )
  return calls
}

const ok = () => ({ ok: true, status: 200, text: async () => PAGE }) as Response
const notFound = () => ({ ok: false, status: 404, statusText: 'Not Found' }) as Response

async function renderPanel() {
  const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
  const { ProcessPanel } = await import('../components/ProcessPanel')
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ProcessPanel runId="run_suite" />
    </QueryClientProvider>,
  )
}

describe('api.processHtml (static export)', () => {
  it('reads the .html file next to the JSON, relative to the default data base', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    const calls = stubFetch(ok)
    const { api } = await import('../lib/api')
    expect(await api.processHtml('run_suite')).toBe(PAGE)
    expect(calls).toEqual(['data/runs_run_suite_process_html.html'])
  })

  it('reads it from a live ?dataBase= override', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    const calls = stubFetch(ok)
    const { api, applyDataBaseOverride } = await import('../lib/api')
    applyDataBaseOverride('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    await api.processHtml('run_suite')
    expect(calls).toEqual(['https://example.test/live/data/runs_run_suite_process_html.html'])
  })
})

describe('ProcessPanel', () => {
  it('live backend: loads the /api/* route as the iframe src, and fetches nothing itself', async () => {
    const calls = stubFetch(ok)
    await renderPanel()
    const frame = screen.getByTitle('Optimizer process snapshot')
    expect(frame.getAttribute('src')).toBe('/api/runs/run_suite/process-html')
    expect(frame.hasAttribute('srcdoc')).toBe(false)
    expect(calls).toEqual([])
  })

  it('static export: renders the exported document through srcdoc, with no /api/ src', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    stubFetch(ok)
    await renderPanel()
    const frame = await screen.findByTitle('Optimizer process snapshot')
    expect(frame.getAttribute('srcdoc')).toBe(PAGE)
    expect(frame.hasAttribute('src')).toBe(false)
    expect(frame.getAttribute('sandbox')).toBe('allow-scripts')
  })

  it('static export without the file: says so instead of an empty frame', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    stubFetch(notFound)
    await renderPanel()
    expect(await screen.findByText(/not in this export/)).toBeInTheDocument()
    expect(screen.queryByTitle('Optimizer process snapshot')).not.toBeInTheDocument()
  })
})
