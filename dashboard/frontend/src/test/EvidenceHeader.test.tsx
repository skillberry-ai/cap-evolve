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

  // --- the #234 review's merged-header contradiction --------------------------

  it('never shows a phase as active when liveness says the run is dead', () => {
    // Merged with #218 the header rendered "● Optimize" (lit, aria-current) beside a
    // `crashed` StatusBadge, and the reader could not tell which was true.
    for (const status of ['crashed', 'stalled'] as const) {
      const { container, unmount } = render(<EvidenceHeader detail={detail()} liveness={status} />)
      const pipeline = container.querySelector('[data-testid="phase-pipeline"]')!
      expect(pipeline.textContent).toContain('(interrupted')
      expect(pipeline.textContent).not.toContain('(active)')
      // nothing claims to be the step the user is currently on
      expect(pipeline.querySelectorAll('[aria-current="step"]')).toHaveLength(0)
      unmount()
    }
  })

  it('leaves the active phase alone while the run is live', () => {
    // #221's plateau dimension is orthogonal: "live and plateaued" is a coherent pair.
    render(<EvidenceHeader detail={detail()} liveness="live" />)
    const pipeline = screen.getByTestId('phase-pipeline')
    expect(pipeline.textContent).toContain('(active)')
    expect(pipeline.querySelectorAll('[aria-current="step"]')).toHaveLength(1)
  })

  it('renders unknown and errored phases as neither done nor skipped', () => {
    const base = detail()
    render(
      <EvidenceHeader
        detail={detail({
          pipeline: {
            ...base.summary.pipeline!,
            phases: [phase('check', 'unknown'), phase('optimize', 'errored')],
          },
        })}
      />,
    )
    const pipeline = screen.getByTestId('phase-pipeline')
    // the words, not the colour, carry it
    expect(pipeline.textContent).toContain('no event attests this phase')
    expect(pipeline.textContent).toContain('errored')
    expect(pipeline.textContent).not.toContain('(done)')
    expect(pipeline.textContent).not.toContain('(skipped)')
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

  // The old `lower_is_better` test asserted a value the backend cannot emit — the
  // hardcoded `metric_direction` had no producer (#234 nit 6). Reward is
  // higher-is-better, so assert THAT: a falling series reads as a regression.
  it('states higher-is-better and reads a falling series as a regression', () => {
    const { container } = render(<Sparkline values={[0.9, 0.1]} />)
    const [p0, p1] = container.querySelector('polyline')!.getAttribute('points')!.split(' ')
    expect(Number(p1.split(',')[1])).toBeGreaterThan(Number(p0.split(',')[1])) // y grows = down
    expect(sparklineLabel([0.9, 0.1])).toContain('regressed')
    expect(sparklineLabel([0.1, 0.9])).toContain('improved')
    expect(container.textContent).toContain('higher is better')
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
    // …and even in the fallback the hard gate is never a green tick: a pre-#138 payload
    // has no event log, so nothing there can attest it (#234 finding 1).
    expect(steps.find((s) => s.key === 'check')!.status).toBe('unknown')
  })

  it('carries errored/interrupted/unknown through without softening them', () => {
    const base = detail()
    const d = detail({
      pipeline: {
        ...base.summary.pipeline!,
        phases: [phase('check', 'unknown'), phase('optimize', 'errored'), phase('finalize', 'interrupted')],
      },
    })
    expect(derivePhases(d).map((s) => s.status)).toEqual(['unknown', 'errored', 'interrupted'])
  })
})
