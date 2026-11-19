/**
 * #676: a multi-objective run's declared objectives/gate_mode must be promoted into
 * their own card, not left to a raw key/value row — and a single-objective run (no
 * `objectives` key at all) must render exactly as before (no card).
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfigPanel } from '../components/ConfigPanel'
import type { RunSummaryDetail } from '../lib/types'

function summaryWithSpec(items: { key: string; value: unknown }[]): RunSummaryDetail {
  return {
    baseline_val: null,
    best_val: null,
    delta_pct: null,
    test_reward: null,
    config: {
      project_dir: '/p',
      spec_missing: false,
      spec_groups: [{ group: 'Metrics & display', items }],
      project_md: null,
      files: [],
    },
  }
}

describe('ConfigPanel', () => {
  it('shows an Objectives card with name + direction when objectives are declared', () => {
    render(
      <ConfigPanel
        summary={summaryWithSpec([
          { key: 'objectives', value: [{ name: 'reward', direction: 'maximize' }, { name: 'cost', direction: 'minimize' }] },
          { key: 'gate_mode', value: 'pareto' },
        ])}
      />,
    )
    expect(screen.getByText('Objectives')).toBeInTheDocument()
    expect(screen.getByText('reward ↑ maximize')).toBeInTheDocument()
    expect(screen.getByText('cost ↓ minimize')).toBeInTheDocument()
    expect(screen.getByText(/gate_mode: pareto/)).toBeInTheDocument()
  })

  it('omits the Objectives card entirely for a single-objective run (no objectives key)', () => {
    render(<ConfigPanel summary={summaryWithSpec([{ key: 'metric_primary', value: 'reward' }])} />)
    expect(screen.queryByText('Objectives')).not.toBeInTheDocument()
  })

  it('shows the spec error (file + line) when the spec could not be read', () => {
    const s = summaryWithSpec([])
    s.config = { ...s.config!, spec_groups: [], spec_error: 'invalid YAML in /p/capevolve.yaml, line 3: unclosed quote' }
    render(<ConfigPanel summary={s} />)
    expect(screen.getByRole('alert')).toHaveTextContent('The spec could not be read')
    expect(screen.getByText(/capevolve\.yaml, line 3/)).toBeInTheDocument()
    expect(screen.queryByText('intervention')).not.toBeInTheDocument()
  })

  it('shows no spec error card when the spec read fine', () => {
    render(<ConfigPanel summary={summaryWithSpec([{ key: 'intervention', value: 'direct' }])} />)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
