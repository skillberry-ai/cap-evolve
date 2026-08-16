import { describe, expect, it } from 'vitest'
import { passKHint, verdictBreakdown } from '../components/KpiStrip'

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

it('renders nothing when handed a dict of non-finite values (the NaN% defect)', () => {
  expect(passKHint({ '1': NaN as unknown as number })).toBeUndefined()
  expect(passKHint({ '1': Infinity as unknown as number })).toBeUndefined()
})

it('never lets a junk value reach the output', () => {
  const out = passKHint({ '1': 0.8, '2': NaN as unknown as number })
  expect(out).toBe('pass^1 80.0%')
  expect(out).not.toMatch(/NaN/)
})

// The static `run_full` export has no `indecisive` key: interpolating it rendered
// `undefined indecisive` in the verdicts fact. Same defect class as `pass^k NaN%`.
describe('verdictBreakdown', () => {
  it('drops a category the payload never counted', () => {
    const out = verdictBreakdown({ accepted: 5, rejected: 5, failed: 0, seed: 1, total: 11 })
    expect(out).toBe('5 accept · 5 reject · 0 no-measure')
    expect(out).not.toMatch(/undefined|NaN/)
  })

  it('keeps a measured indecisive count', () => {
    expect(
      verdictBreakdown({ accepted: 1, rejected: 0, indecisive: 2, failed: 0, seed: 1, total: 4 }),
    ).toBe('1 accept · 0 reject · 2 indecisive · 0 no-measure')
  })

  it('is undefined when nothing was counted', () => {
    expect(
      verdictBreakdown({
        accepted: NaN as unknown as number,
        rejected: undefined as unknown as number,
        failed: undefined as unknown as number,
        seed: 0,
        total: 0,
      }),
    ).toBeUndefined()
  })
})
