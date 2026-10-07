import { describe, expect, it } from 'vitest'
import { getGateMode, getObjectives } from '../lib/objectives'
import type { RunSummaryDetail } from '../lib/types'

function summaryWithConfig(groups: { group: string; items: { key: string; value: unknown }[] }[]): RunSummaryDetail {
  return {
    baseline_val: null,
    best_val: null,
    delta_pct: null,
    test_reward: null,
    config: { project_dir: '/p', spec_missing: false, spec_groups: groups, project_md: null, files: [] },
  }
}

describe('getObjectives', () => {
  it('returns [] when the run declares no objectives', () => {
    expect(getObjectives(summaryWithConfig([]))).toEqual([])
    expect(getObjectives(undefined)).toEqual([])
  })

  it('normalizes name + direction, defaulting direction to maximize', () => {
    const s = summaryWithConfig([
      { group: 'Metrics & display', items: [{ key: 'objectives', value: [{ name: 'reward' }, { name: 'cost', direction: 'minimize' }] }] },
    ])
    expect(getObjectives(s)).toEqual([
      { name: 'reward', direction: 'maximize' },
      { name: 'cost', direction: 'minimize' },
    ])
  })

  it('drops malformed entries instead of faking a name', () => {
    const s = summaryWithConfig([
      { group: 'Other', items: [{ key: 'objectives', value: ['reward', { direction: 'minimize' }, { name: 'cost', direction: 'minimize' }] }] },
    ])
    expect(getObjectives(s)).toEqual([{ name: 'cost', direction: 'minimize' }])
  })
})

describe('getGateMode', () => {
  it('reads gate_mode wherever it landed', () => {
    const s = summaryWithConfig([{ group: 'Budget & gate', items: [{ key: 'gate_mode', value: 'pareto' }] }])
    expect(getGateMode(s)).toBe('pareto')
  })

  it('returns null when absent', () => {
    expect(getGateMode(summaryWithConfig([]))).toBeNull()
  })
})
