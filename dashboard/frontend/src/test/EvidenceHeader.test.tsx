import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidenceHeader } from '../components/EvidenceHeader'
import { Sparkline, sparklineLabel } from '../components/Sparkline'
import { derivePhases } from '../lib/phases'
import type { GraphNode, PipelinePhase, RunDetail } from '../lib/types'

const phase = (key: string, status: PipelinePhase['status']): PipelinePhase => ({
  key,
  label: key,
  status,
  detail: `${key} detail`,
  started_at: 1000,
  index: 1,
})

function node(id: string, iteration: number, val: number): GraphNode {
  return { id, parent: 'seed', children: [], status: 'accepted', val, iteration }
}

const detail = (over: Partial<RunDetail['summary']> = {}, nodes: GraphNode[] = []): RunDetail => ({
  run_id: 'run_x',
  path: '/run_x',
  graph: { nodes, root: 'seed', best_id: null },
  summary: {
    baseline_val: 0.2,
    best_val: 0.8,
    delta_pct: 300,
    test_reward: null,
    algorithm: 'gepa',
    metric_direction: 'higher_is_better',
    pipeline: {
      phases: [phase('baseline', 'done'), phase('optimize', 'active'), phase('finalize', 'pending')],
      current: 'optimize',
      now: { line: '[12:00:00] ACCEPT  c1  val=0.8000 (parent 0.2000)', t: 1000, since: 900 },
      burn: {
        usd: 0.81,
        tokens: 11700,
        elapsed_seconds: 120,
        usd_per_min: 0.405,
        tokens_per_min: 5850,
        source: 'spent',
      },
    },
    ...over,
  },
})

describe('EvidenceHeader', () => {
  it('renders the pipeline with the active phase lit and marked for a11y', () => {
    render(<EvidenceHeader detail={detail()} />)
    const pipeline = screen.getByTestId('phase-pipeline')
    // status is text, not colour: the sr-only suffix names it for every stage
    expect(pipeline.textContent).toContain('(done)')
    expect(pipeline.textContent).toContain('(active)')
    expect(pipeline.textContent).toContain('(pending)')
    // exactly one stage carries aria-current="step"
    expect(pipeline.querySelectorAll('[aria-current="step"]')).toHaveLength(1)
    // the algorithm name is appended to Optimize
    expect(pipeline.textContent).toContain('gepa')
  })

  it('renders the now line verbatim from the backend (already sanitised)', () => {
    render(<EvidenceHeader detail={detail()} />)
    expect(screen.getByTestId('now-line').textContent).toContain('ACCEPT  c1  val=0.8000')
  })

  it('shows the burn readout and its rate, attributed to state.json Spent', () => {
    render(<EvidenceHeader detail={detail()} />)
    expect(screen.getByText('$0.810')).toBeTruthy()
    expect(screen.getByText('11.7K')).toBeTruthy()
    expect(screen.getByText('$0.405/min')).toBeTruthy()
    const cell = screen.getByText('burn').parentElement!
    expect(cell.getAttribute('title')).toContain('state.json Spent.total_usd')
  })

  it('attributes every evidence-line number to its source file', () => {
    render(<EvidenceHeader detail={detail()} />)
    const line = screen.getByTestId('evidence-line')
    expect(line.textContent).toContain('baseline (seed on val)')
    expect(line.textContent).toContain('20.0%')
    expect(line.textContent).toContain('80.0%')
    expect(line.textContent).toContain('+300.0%')
    expect(line.textContent).toContain('not finalized')
    expect(line.textContent).toContain('higher is better')
    expect(screen.getByText('baseline (seed on val)').parentElement!.getAttribute('title'))
      .toContain('baseline.json')
    expect(screen.getByText('sealed test').parentElement!.getAttribute('title'))
      .toContain('final.json')
  })

  it('shows POINTS, not a fake %, when the baseline is zero', () => {
    // reduce_run leaves delta_pct null off a zero baseline (a % change is undefined
    // there); rendering signedPct(delta_abs*100) as "%" would have claimed +100.0%.
    render(<EvidenceHeader detail={detail({ baseline_val: 0, best_val: 1, delta_pct: null, delta_abs: 1 })} />)
    const line = screen.getByTestId('evidence-line')
    expect(line.textContent).toContain('+100.0 pts')
    expect(line.textContent).not.toContain('+100.0%')
  })

  it('omits the burn rate when the backend reports none (finished / sub-minute run)', () => {
    const base = detail()
    render(
      <EvidenceHeader
        detail={detail({
          pipeline: { ...base.summary.pipeline!, burn: { ...base.summary.pipeline!.burn, usd_per_min: null, tokens_per_min: null } },
        })}
      />,
    )
    expect(screen.getByText('$0.810')).toBeTruthy()
    expect(screen.queryByText(/\/min/)).toBeNull()
  })

  it('shows the sealed test once finalize ran', () => {
    render(<EvidenceHeader detail={detail({ test_reward: 0.75, test_sealed: true })} />)
    expect(screen.getByTestId('evidence-line').textContent).toContain('75.0%')
  })

  it('degrades to the evidence line when the payload predates #138', () => {
    render(<EvidenceHeader detail={detail({ pipeline: undefined })} />)
    expect(screen.queryByTestId('phase-pipeline')).toBeNull()
    expect(screen.getByTestId('evidence-line').textContent).toContain('20.0%')
  })

  it('draws the sparkline from the running-best curve', () => {
    render(<EvidenceHeader detail={detail({}, [node('c1', 1, 0.4), node('c2', 2, 0.8)])} />)
    const svg = screen.getByTestId('sparkline')
    expect(svg.querySelector('polyline')!.getAttribute('points')!.split(' ')).toHaveLength(2)
    expect(svg.getAttribute('aria-label')).toContain('improved from 40.0% to 80.0%')
  })
})

describe('Sparkline', () => {
  it('gives the shape a text equivalent, not colour alone', () => {
    render(<Sparkline values={[0.1, 0.5, 0.9]} />)
    const svg = screen.getByTestId('sparkline')
    expect(svg.getAttribute('role')).toBe('img')
    expect(svg.getAttribute('aria-label')).toBe(sparklineLabel([0.1, 0.5, 0.9]))
    // and the direction is also words on screen, not just an arrow glyph
    expect(screen.getByText(/higher is better/)).toBeTruthy()
  })

  it('says so in words rather than drawing a misleading flat line', () => {
    render(<Sparkline values={[0.5]} />)
    expect(screen.queryByTestId('sparkline')).toBeNull()
    expect(screen.getByTestId('sparkline-empty').textContent).toContain('Best score over 1')
  })

  it('renders nothing animated (nothing for prefers-reduced-motion to suppress)', () => {
    const { container } = render(<Sparkline values={[0.1, 0.9]} />)
    expect(container.querySelectorAll('animate, animateTransform')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('animate-')
  })

  it('inverts y for lower-is-better so up-and-right always means better', () => {
    const { container } = render(<Sparkline values={[0.9, 0.1]} direction="lower_is_better" />)
    const [p0, p1] = container.querySelector('polyline')!.getAttribute('points')!.split(' ')
    expect(Number(p1.split(',')[1])).toBeLessThan(Number(p0.split(',')[1])) // y shrinks = up
    expect(sparklineLabel([0.9, 0.1], 'lower_is_better')).toContain('improved')
  })
})

describe('derivePhases with the backend pipeline', () => {
  it('uses the backend statuses verbatim and attaches display metrics', () => {
    const steps = derivePhases(detail())
    expect(steps.map((s) => [s.key, s.status])).toEqual([
      ['baseline', 'done'],
      ['optimize', 'active'],
      ['finalize', 'pending'],
    ])
    expect(steps[0].metrics).toEqual([{ label: 'seed val', value: '20.0%' }])
    expect(steps[1].label).toContain('gepa')
  })

  it('carries a skipped phase through rather than calling it pending', () => {
    const d = detail({
      pipeline: {
        ...detail().summary.pipeline!,
        phases: [phase('intake', 'skipped'), phase('finalize', 'done')],
      },
    })
    expect(derivePhases(d)[0].status).toBe('skipped')
  })

  it('falls back to summary-shaped inference without a pipeline', () => {
    const steps = derivePhases(detail({ pipeline: undefined }))
    expect(steps.map((s) => s.key)).toEqual([
      'intake',
      'check',
      'baseline',
      'algorithm',
      'finalize',
      'report',
    ])
  })
})
