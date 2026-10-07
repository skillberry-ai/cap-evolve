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

  // dashboard.py's _compute_outcomes shape: {task_id: status}
  const mockOutcomes: Outcomes = {
    task1: 'fixed',
    task2: 'fixed',
    task4: 'broke',
    task3: 'still_failing',
    task5: 'still_passing',
    task6: 'still_passing',
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

    expect(screen.getByText('Validation Warnings')).toBeInTheDocument()
    expect(screen.getByText(/Unknown task ID: task99/)).toBeInTheDocument()
    expect(screen.getByText(/Edit E3 references missing cluster C/)).toBeInTheDocument()
  })

  // #625: the compact shape optimizers really write — verbatim from
  // .capevolve/run_full/candidates/cand_11/DIAGNOSIS.json (trimmed to 2 clusters/2 skips):
  // clusters[].edit is a string, no top-level edits/techniques, skipped is a {task: reason} map.
  const realDiagnosis: Diagnosis = {
    headline: '24+44+18 fixes',
    clusters: [
      {
        id: 'M',
        name: 'free bags dropped at booking',
        tasks: ['24'],
        tag: 'KNOWLEDGE (policy told agent to copy only nonfree_baggages)',
        edit: 'quote_booking returns total_baggages; policy copy it + use free allowance',
        evidence: '24 cand_6 t0,t3,t7: quote free_baggages 1, told user 1 free bag, booked total_baggages=0',
      },
      {
        id: 'N',
        name: 'segment durations summed',
        tasks: ['44'],
        tag: 'RULE-VIOLATION -> computed field',
        edit: 'get_user_reservations max_flight_duration_hours + explicit per-flight rule with example',
        evidence: "44 cand_6 t0,t2: 'NM1VX1 total 6.0h -> no change'; gold upgrades it (3.0+3.0)",
      },
    ],
    skipped: {
      '23': 'judge flakiness, db_match 1',
      '39': 'gold conflicts with 44',
    },
  }

  it('renders the real compact DIAGNOSIS.json shape without crashing (#625)', () => {
    render(
      <DiagnosisFlow
        diagnosis={realDiagnosis}
        outcomes={{ '24': 'fixed', '44': 'still_failing', '7': 'broke', '2': 'still_passing' }}
      />,
    )
    expect(screen.getByText('Tasks (2)')).toBeInTheDocument()
    expect(screen.getByText('1 not predicted')).toBeInTheDocument()
    expect(screen.getByText('free bags dropped at booking')).toBeInTheDocument()
    expect(
      screen.getByText('quote_booking returns total_baggages; policy copy it + use free allowance'),
    ).toBeInTheDocument()
    expect(screen.getByText(/booked total_baggages=0/)).toBeInTheDocument()
    expect(screen.getByText('Edits (2)')).toBeInTheDocument()
    expect(screen.getByText('Skipped edits (2)')).toBeInTheDocument()
    expect(screen.getByText('gold conflicts with 44')).toBeInTheDocument()
  })

  it('renders a cluster-only diagnosis with no edit strings (#625)', () => {
    render(<DiagnosisFlow diagnosis={{ headline: 'h', clusters: [{ id: 'P', name: 'p', tasks: ['1'] }] }} />)
    expect(screen.getByText('Edits (0)')).toBeInTheDocument()
  })

  // #676: the task column groups by root-cause cluster, plus catch-all groups for a
  // failing task no cluster named and a regression no cluster predicted.
  it('groups failing-not-in-any-cluster and unpredicted-regression tasks (#676)', () => {
    const diag: Diagnosis = {
      headline: 'h',
      clusters: [{ id: 'A', name: 'cluster A', tasks: ['task1'] }],
      edits: [],
    }
    const outcomes: Outcomes = {
      task1: 'fixed',
      task2: 'still_failing', // failing, not named by any cluster
      task4: 'broke', // regression not named by any cluster
    }
    render(<DiagnosisFlow diagnosis={diag} outcomes={outcomes} />)
    expect(screen.getByText('failing, not in any cluster')).toBeInTheDocument()
    expect(screen.getByText('regressions (were passing)')).toBeInTheDocument()
    expect(screen.getByText('task2')).toBeInTheDocument()
    expect(screen.getByText('task4')).toBeInTheDocument()
  })

  it('marks a latent cluster (no currently-failing task) as a preventive fix (#676)', () => {
    const diag: Diagnosis = {
      headline: 'h',
      clusters: [{ id: 'L', name: 'preventive cluster', tasks: ['task9'], latent: true }],
      edits: [],
    }
    render(<DiagnosisFlow diagnosis={diag} outcomes={{ task9: 'still_passing' }} />)
    expect(screen.getByText('latent')).toBeInTheDocument()
  })
})
