import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from '../components/StatusBadge'

describe('StatusBadge (#118)', () => {
  it('renders the two new states with a distinct label, not as a finish', () => {
    render(<StatusBadge status="stalled" detail="STALLED — no events for 42.0m" />)
    expect(screen.getByText('stalled')).toBeTruthy()
    expect(screen.getByTitle('STALLED — no events for 42.0m')).toBeTruthy()
  })

  it('renders crashed distinctly from failed', () => {
    const { container } = render(<StatusBadge status="crashed" />)
    expect(container.textContent).toBe('crashed')
  })

  it('a finished run still reads done', () => {
    const { container } = render(<StatusBadge status="done" />)
    expect(container.textContent).toBe('done')
  })
})
