/**
 * The run header's two claims about time. A live run's "elapsed" has no end yet, and
 * rendering it like a total is how a nine-minute-old spreadsheetbench job came to read
 * "0s elapsed" (run 33492876620).
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RunHeader } from '../components/RunHeader'
import type { RunSummaryDetail } from '../lib/types'

const summary = (over: Partial<RunSummaryDetail> = {}): RunSummaryDetail =>
  ({
    run_id: 'run_suite',
    algorithm: 'agent-optimize',
    status: 'running',
    baseline_val: null,
    best_val: null,
    delta_pct: null,
    test_reward: null,
    ...over,
  }) as RunSummaryDetail

describe('RunHeader', () => {
  it('marks a live run\'s elapsed time as open-ended', () => {
    render(<RunHeader runId="run_suite" summary={summary({ elapsed_seconds: 557, elapsed_open: true })} />)
    expect(screen.getByText(/elapsed so far/)).toBeInTheDocument()
  })

  it('reports a finished run\'s elapsed time as a total', () => {
    render(
      <RunHeader
        runId="run_suite"
        summary={summary({ status: 'completed', elapsed_seconds: 557, elapsed_open: false })}
      />,
    )
    expect(screen.getByText(/557|9m/)).toBeInTheDocument()
    expect(screen.queryByText(/elapsed so far/)).toBeNull()
  })

  it('shows the running badge for a run whose baseline is still being scored', () => {
    render(
      <RunHeader
        runId="run_suite"
        summary={summary({ status_reason: "the seed's baseline is still being scored" })}
      />,
    )
    expect(screen.getByText('running')).toBeInTheDocument()
    expect(screen.queryByText('failed')).toBeNull()
  })
})
