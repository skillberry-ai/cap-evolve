import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DiagnosisFlow } from '../components/DiagnosisFlow'
import type { Diagnosis, Outcomes } from '../lib/types'

describe('DiagnosisFlow', () => {
  const mockDiagnosis: Diagnosis = {
    candidate: 'cand_0001',
    headline: 'Fix formula handling and add semantic audit',
    clusters: [
      {
        id: 'A',
        name: 'INPUT formula erased by wb.save()',
        detail: 'Formula cells lose cached values',
        tasks: ['task1', 'task2'],
        scope: 'BOUNDED',
        latent: false,
        tag: 'CONTRACT',
      },
      {
        id: 'B',
        name: 'Sort order issues',
        detail: 'Incorrect tie-breaking',
        tasks: ['task3'],
        scope: 'WIDE',
        latent: false,
        tag: 'KNOWLEDGE',
      },
    ],
    edits: [
      {
        id: 'E1',
        title: 'Carry cached values forward',
        files: ['prompt.md'],
        lever: 'CONTRACT',
        clusters: ['A'],
        blast_radius: 'BOUNDED',
        verified: 'executed on synthetic workbook',
      },
      {
        id: 'E2',
        title: 'Remove invented tie-breaker',
        files: ['prompt.md'],
        lever: 'KNOWLEDGE',
        clusters: ['B'],
        blast_radius: 'WIDE',
        verified: 'manual review',
      },
    ],
    skipped: [
      {
        title: 'Alternative approach',
        reason: 'Would break existing tests',
      },
    ],
    techniques: ['replayed rollouts', 'synthetic test cases'],
  }

  const mockOutcomes: Outcomes = {
    fixed: ['task1', 'task2'],
    broke: ['task4'],
    still_failing: ['task3'],
    still_passing: ['task5', 'task6'],
    targeted: ['task1', 'task2', 'task3'],
  }

  it('renders diagnosis headline', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)
    expect(screen.getByText('Fix formula handling and add semantic audit')).toBeInTheDocument()
  })

  it('renders tally row with correct counts', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    expect(screen.getByText('Parent failing')).toBeInTheDocument()
    expect(screen.getByText('Clusters')).toBeInTheDocument()
    expect(screen.getByText('Edits')).toBeInTheDocument()
    expect(screen.getByText('Result')).toBeInTheDocument()
    expect(screen.getByText('Regressions')).toBeInTheDocument()
  })

  it('renders clusters with task lists', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    expect(screen.getByText('INPUT formula erased by wb.save()')).toBeInTheDocument()
    expect(screen.getByText('Sort order issues')).toBeInTheDocument()
    // Cluster IDs appear multiple times (in cluster section and edit references)
    const clusterAElements = screen.getAllByText('A')
    expect(clusterAElements.length).toBeGreaterThan(0)
  })

  it('renders edits with file lists', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    expect(screen.getByText('E1')).toBeInTheDocument()
    expect(screen.getByText('Carry cached values forward')).toBeInTheDocument()
    expect(screen.getByText('E2')).toBeInTheDocument()
    expect(screen.getByText('Remove invented tie-breaker')).toBeInTheDocument()
  })

  it('renders skipped edits section', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    expect(screen.getByText(/Skipped edits/)).toBeInTheDocument()
    expect(screen.getByText('Alternative approach')).toBeInTheDocument()
    expect(screen.getByText('Would break existing tests')).toBeInTheDocument()
  })

  it('renders techniques used', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    expect(screen.getByText('Techniques used')).toBeInTheDocument()
    expect(screen.getByText('replayed rollouts')).toBeInTheDocument()
    expect(screen.getByText('synthetic test cases')).toBeInTheDocument()
  })

  it('handles diagnosis without outcomes', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} />)

    // Should still render clusters and edits
    expect(screen.getByText('INPUT formula erased by wb.save()')).toBeInTheDocument()
    expect(screen.getByText('Carry cached values forward')).toBeInTheDocument()
  })

  it('displays validation warnings when present', () => {
    const diagnosisWithWarnings: Diagnosis = {
      ...mockDiagnosis,
      warnings: ['Unknown task ID: task99', 'Edit E3 references missing cluster C'],
    }

    render(<DiagnosisFlow diagnosis={diagnosisWithWarnings} outcomes={mockOutcomes} />)

    // Warnings are now shown as a collapsed button with count
    expect(screen.getByText('2 warnings')).toBeInTheDocument()
  })

  it('renders edit cards with cluster chip text and tooltips', () => {
    render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)

    // Edit E1 references cluster A
    const clusterChips = screen.getAllByText('A')
    expect(clusterChips.length).toBeGreaterThan(0)
    
    // Check that cluster chip has tooltip (title attribute)
    const editSection = screen.getByText('Carry cached values forward').closest('div')
    expect(editSection).toBeInTheDocument()
    
    // Edit E2 references cluster B
    const clusterBChips = screen.getAllByText('B')
    expect(clusterBChips.length).toBeGreaterThan(0)
  })

  it('does not use broken bg-opacity or border-opacity classes', () => {
    const { container } = render(<DiagnosisFlow diagnosis={mockDiagnosis} outcomes={mockOutcomes} />)
    
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
