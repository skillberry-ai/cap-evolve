import { describe, expect, it } from 'vitest'
import { passKHint } from '../components/KpiStrip'

// Issue #112: never render a k that wasn't measured, never drop one that was.
describe('passKHint', () => {
  it('renders a non-default ks without inventing pass^2', () => {
    const h = passKHint({ '1': 0.9, '3': 0.4 })
    expect(h).toContain('pass^3 40.0%') // measured — must be shown
    expect(h).not.toContain('pass^2') // never requested — must NOT be fabricated
    expect(h).toBe('pass^1 90.0% · pass^3 40.0%')
  })

  it('renders only k=1 for a single-trial run', () => {
    // was 'pass^1 100.0% · pass^2 N/A' under the hardcoded Math.max(maxK, 2) floor
    expect(passKHint({ '1': 1.0 })).toBe('pass^1 100.0%')
  })

  it('sorts numerically, not lexically', () => {
    expect(passKHint({ '10': 0.1, '2': 0.5 })).toBe('pass^2 50.0% · pass^10 10.0%')
  })

  it('is undefined when there is nothing measured', () => {
    expect(passKHint(null)).toBeUndefined()
    expect(passKHint(undefined)).toBeUndefined()
    expect(passKHint({})).toBeUndefined()
  })
})
