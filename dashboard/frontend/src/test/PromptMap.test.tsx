import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PromptMap } from '../components/PromptMap'
import type { PromptMap as PromptMapType } from '../lib/types'

describe('PromptMap', () => {
  const mockPromptMap: PromptMapType = {
    'prompt.md': {
      lines: 307,
      bytes: 17735,
      headings: [
        [4, 1, 'How your work is graded'],
        [22, 2, 'Rule 1 — compute the value in Python'],
        [46, 2, 'Rule 2 — write only what the instruction asks for'],
      ],
      add: [44, 45, 46, 47, 48],
      rem: [43],
      touched: [
        ['Rule 2 — write only what the instruction asks for', 46],
      ],
    },
    'task_template.md': {
      lines: 50,
      bytes: 2500,
      headings: [
        [1, 1, 'Task Template'],
      ],
      add: [],
      rem: [],
      touched: [],
    },
  }

  it('renders file selector tabs when multiple files', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    // File tabs should be present as buttons
    const buttons = screen.getAllByRole('button')
    const fileButtons = buttons.filter(b => b.textContent === 'prompt.md' || b.textContent === 'task_template.md')
    expect(fileButtons.length).toBe(2)
  })

  it('displays file statistics', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    expect(screen.getByText('307 lines · 17.3KB')).toBeInTheDocument()
  })

  it('shows section map with headings', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    expect(screen.getByText('How your work is graded')).toBeInTheDocument()
    expect(screen.getByText('Rule 1 — compute the value in Python')).toBeInTheDocument()
  })

  it('highlights touched sections', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    // Should show "touched" label for modified sections
    expect(screen.getByText('touched')).toBeInTheDocument()
  })

  it('displays change counts', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    // Should show added/removed line counts (appears in file info and summary)
    const changeElements = screen.getAllByText(/\+5/)
    expect(changeElements.length).toBeGreaterThan(0)
  })

  it('shows summary statistics', () => {
    render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)

    // Summary stats appear in multiple places (per-file and overall)
    const totalLinesElements = screen.getAllByText('Total lines')
    expect(totalLinesElements.length).toBeGreaterThan(0)
  })

  it('handles empty prompt map gracefully', () => {
    const emptyMap: PromptMapType = {}
    render(<PromptMap promptMap={emptyMap} candidateId="cand_0001" runId="run_123" />)

    expect(screen.getByText(/No prompt map data available/)).toBeInTheDocument()
  })

  it('formats bytes correctly', () => {
    const largeFileMap: PromptMapType = {
      'large.md': {
        lines: 10000,
        bytes: 1500000,
        headings: [],
        add: [],
        rem: [],
        touched: [],
      },
    }

    render(<PromptMap promptMap={largeFileMap} candidateId="cand_0001" runId="run_123" />)

    // Should show MB for large files (1500000 bytes = 1.4MB, appears multiple times)
    const mbElements = screen.getAllByText(/1\.[0-9]MB/)
    expect(mbElements.length).toBeGreaterThan(0)
  })

  it('does not use broken bg-opacity or border-opacity classes', () => {
    const { container } = render(<PromptMap promptMap={mockPromptMap} candidateId="cand_0001" runId="run_123" />)
    
    // Check that no element has bg-opacity-* or border-opacity-* classes
    const allElements = container.querySelectorAll('*')
    allElements.forEach(element => {
      const className = element.className
      if (typeof className === 'string') {
        expect(className).not.toMatch(/\b(bg|border)-opacity-\d+/)
      }
    })
  })
})
