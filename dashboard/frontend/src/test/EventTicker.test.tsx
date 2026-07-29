import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EventTicker } from '../components/EventTicker'
import { initialStreamState, streamReducer } from '../lib/useRunStream'

/** Drive the real reducer so the test covers the same log shape the SPA renders. */
function logOf(...events: Record<string, unknown>[]) {
  let s = streamReducer(initialStreamState, { type: 'open' })
  for (const data of events) s = streamReducer(s, { type: 'event', data })
  return s.log
}

describe('EventTicker', () => {
  it('renders each event kind with its candidate, val and reason', () => {
    render(
      <EventTicker
        log={logOf(
          { kind: 'step', candidate: 'cand_0001', accept: true, val: 0.75, reason: 'up' },
          { kind: 'optimizer_error', candidate_id: 'cand_0002', error: 'boom' },
        )}
      />,
    )
    expect(screen.getByText('step')).toBeInTheDocument()
    expect(screen.getByText(/cand_0001 · val 75\.0% · up/)).toBeInTheDocument()
    expect(screen.getByText('optimizer_error')).toBeInTheDocument()
    // candidate_id is normalised the same way the backend reducer does it
    expect(screen.getByText(/cand_0002 · boom/)).toBeInTheDocument()
  })

  it('shows the newest event first', () => {
    render(<EventTicker log={logOf({ kind: 'first' }, { kind: 'second' })} />)
    const kinds = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(kinds[0]).toContain('second')
    expect(kinds[1]).toContain('first')
  })

  it('degrades to an empty message with no events', () => {
    render(<EventTicker log={[]} />)
    expect(screen.getByText(/No live events yet/)).toBeInTheDocument()
  })
})
