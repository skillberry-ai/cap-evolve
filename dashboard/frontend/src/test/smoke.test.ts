import { describe, expect, it } from 'vitest'
import { prefersReducedMotion } from '../lib/motion'

describe('test harness', () => {
  it('runs and motion guard resolves to a boolean', () => {
    expect(typeof prefersReducedMotion()).toBe('boolean')
  })
})
