import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { applyDataBaseOverride, isLiveOverride } from '../lib/api'

type WindowOverride = { __CAPEVOLVE_DATA_BASE__?: string; __CAPEVOLVE_STATIC__?: unknown }

afterEach(() => {
  const w = window as unknown as WindowOverride
  delete w.__CAPEVOLVE_DATA_BASE__
  delete w.__CAPEVOLVE_STATIC__
  vi.unstubAllGlobals()
})

describe('applyDataBaseOverride', () => {
  it('sets window.__CAPEVOLVE_DATA_BASE__ from a dataBase query param', () => {
    applyDataBaseOverride('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    expect((window as unknown as WindowOverride).__CAPEVOLVE_DATA_BASE__).toBe(
      'https://example.test/live/data',
    )
  })

  it('leaves the override unset when there is no dataBase param', () => {
    applyDataBaseOverride('?foo=bar')
    expect((window as unknown as WindowOverride).__CAPEVOLVE_DATA_BASE__).toBeUndefined()
  })
})

describe('isLiveOverride', () => {
  it('is true once a dataBase override is set', () => {
    applyDataBaseOverride('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    expect(isLiveOverride()).toBe(true)
  })

  it('is false with no override set', () => {
    expect(isLiveOverride()).toBe(false)
  })
})

// STATIC_MODE is captured once at module-evaluation time (matching real deployment,
// where a static export's index.html sets window.__CAPEVOLVE_STATIC__ *before* the
// bundle loads). vi.resetModules() + a fresh dynamic import reproduces that ordering
// per test instead of reusing the already-evaluated module from the static import above.
describe('getJSON static-mode base', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('fetches from the overridden data base when set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return { ok: true, json: async () => [] } as Response
      }),
    )
    const { api, applyDataBaseOverride: apply } = await import('../lib/api')
    apply('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    await api.runs()
    expect(calls[0]).toBe('https://example.test/live/data/runs.json')
  })

  it('falls back to the relative "data" base when no override is set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        calls.push(url)
        return { ok: true, json: async () => [] } as Response
      }),
    )
    const { api } = await import('../lib/api')
    await api.runs()
    expect(calls[0]).toBe('data/runs.json')
  })

  it('throws LivePendingError (not a plain Error) for a 404 while a dataBase override is set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 404, statusText: 'Not Found' }) as Response),
    )
    const { api, applyDataBaseOverride: apply, LivePendingError: LivePendingErrorCtor } = await import('../lib/api')
    apply('?dataBase=https%3A%2F%2Fexample.test%2Flive%2Fdata')
    await expect(api.run('run_suite')).rejects.toBeInstanceOf(LivePendingErrorCtor)
  })

  it('throws a plain Error (not LivePendingError) for a 404 with no override set', async () => {
    (window as unknown as WindowOverride).__CAPEVOLVE_STATIC__ = true
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: false, status: 404, statusText: 'Not Found' }) as Response),
    )
    const { api, LivePendingError: LivePendingErrorCtor } = await import('../lib/api')
    await expect(api.run('run_suite')).rejects.not.toBeInstanceOf(LivePendingErrorCtor)
  })
})
