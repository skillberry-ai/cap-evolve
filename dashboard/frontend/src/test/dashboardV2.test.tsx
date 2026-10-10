/** Run schema v2 views (#703), against src/test/fixtures/run_v2.json. */
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import fx from './fixtures/run_v2.json'
import { LineageTree } from '../components/LineageTree'
import { layoutLineage } from '../lib/lineage'
import { SeriesCharts, buildSeries } from '../components/SeriesCharts'
import { ParetoScatter } from '../components/ParetoScatter'
import { toObjectivePoints } from '../lib/pareto'
import { TaskMatrix } from '../components/TaskMatrix'
import { DecisionTrail } from '../components/DecisionTrail'
import { DiagnosisFlow } from '../components/DiagnosisFlow'
import { editOutcome } from '../lib/diagnosis'
import { CapDiff } from '../components/CapDiff'
import { api } from '../lib/api'
import type { GraphNode, RunGraph, RunObjectives, RunSummaryDetail, Diagnosis } from '../lib/types'

const graph = fx.graph as unknown as RunGraph
const nodes = graph.nodes as GraphNode[]
const objectives = fx.objectives as unknown as RunObjectives

describe('LineageTree node states', () => {
  it('encodes each eval_state by pattern, with k/N for partial and merge edges from parents[]', () => {
    const { container } = render(<LineageTree graph={graph} />)
    for (const s of ['full', 'partial', 'screened', 'unevaluated']) {
      expect(container.querySelector(`[data-state="${s}"]`)).not.toBeNull()
    }
    expect(screen.getAllByTestId('coverage-mark').map((e) => e.textContent)).toContain('12/30 partial')
    const merge = layoutLineage(graph).edges.filter((e) => e.merge)
    expect(merge).toEqual([{ from: 'cand_3', to: 'cand_6', onSpine: false, merge: true }])
  })
})

describe('SeriesCharts', () => {
  it('defaults to reward + matched cost; optimizer spend is cumulative; gaps stay gaps', () => {
    render(<SeriesCharts nodes={nodes} objectives={objectives} />)
    expect(screen.getByTestId('series-reward')).toBeInTheDocument()
    expect(screen.getByTestId('series-cost_matched_success')).toBeInTheDocument()
    expect(screen.queryByTestId('series-latency_s')).toBeNull()
    fireEvent.click(screen.getByLabelText('Latency'))
    expect(screen.getByTestId('series-latency_s')).toBeInTheDocument()
    const pts = buildSeries(nodes, objectives, true)
    expect(pts.map((p) => p.values.optimizer_cum_usd?.toFixed(2))).toEqual([undefined, '0.42', '0.52', '0.82'])
    expect(pts[3].values.latency_s).toBeUndefined()
  })
})

describe('Pareto view', () => {
  it('builds points from a selectable cost axis and marks tradeoff outcomes', () => {
    const o = { ...objectives, candidates: { ...objectives.candidates, cand_6: { ...objectives.candidates.cand_6, latency_s: 9 } } }
    const pts = toObjectivePoints(nodes, o, 'latency_s')
    expect(pts.find((p) => p.id === 'cand_6')?.tradeoff).toBe(true)
    expect(pts.find((p) => p.id === 'cand_1')?.tradeoff).toBe(false)
    render(<ParetoScatter nodes={nodes} objectives={objectives} />)
    fireEvent.change(screen.getByLabelText('cost axis'), { target: { value: 'cost_matched_success' } })
    expect(screen.getByLabelText('cost axis')).toHaveValue('cost_matched_success')
  })
})

describe('TaskMatrix matched-subset toggle', () => {
  const summary = { tasks: ['3', '7', '22'], objectives: [{ name: 'reward', direction: 'maximize' }, { name: 'cost', direction: 'minimize' }] } as unknown as RunSummaryDetail
  it('greys unmatched tasks and shows per-task dC for matched ones', () => {
    const { container } = render(<TaskMatrix summary={summary} nodes={nodes} selectedId="cand_1" />)
    expect(container.querySelector('[data-matched]')).toBeNull()
    fireEvent.click(screen.getByRole('checkbox'))
    expect(container.querySelector('tr[data-matched="false"]')).toHaveTextContent('22')
    expect(container.querySelector('tr[data-matched="false"]')).toHaveTextContent('one side only')
    expect(container.querySelector('tr[data-matched="true"]')).toHaveTextContent('+$0.002')
  })
  it('has no toggle when the candidate has no matched set', () => {
    render(<TaskMatrix summary={summary} nodes={nodes} selectedId="seed" />)
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})

describe('DecisionTrail (RunTimeline decisions)', () => {
  it('lists every decision with evidence and per-decision optimizer spend', () => {
    render(<DecisionTrail decisions={fx.decisions as never} />)
    const items = screen.getAllByTestId('decision')
    expect(items.map((i) => i.firstElementChild?.textContent?.toLowerCase())).toEqual(['propose', 'screen', 'kill', 'grow', 'merge'])
    expect(items[1]).toHaveAttribute('title', expect.stringContaining('mean_delta: -0.12'))
    expect(items[0]).toHaveTextContent('$0.42')
  })
  it('renders nothing without decisions', () => {
    const { container } = render(<DecisionTrail decisions={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('DiagnosisFlow outcome', () => {
  const diagnosis = { headline: 'h', clusters: [{ id: 'c1', name: 'n', tasks: ['22'] }], edits: [] } as unknown as Diagnosis
  it('flags an edit whose target tasks did not move', () => {
    const c3 = nodes.find((n) => n.id === 'cand_3')!
    expect(editOutcome(c3.edit, c3.outcomes)?.moved).toBe(false)
    render(<DiagnosisFlow diagnosis={diagnosis} outcomes={c3.outcomes} edit={c3.edit} />)
    expect(screen.getByTestId('edit-outcome')).toHaveTextContent('FLAG: edit did not move its target tasks')
  })
  it('reports a moved target', () => {
    const c1 = nodes.find((n) => n.id === 'cand_1')!
    render(<DiagnosisFlow diagnosis={diagnosis} outcomes={c1.outcomes} edit={c1.edit} />)
    expect(screen.getByTestId('edit-outcome')).toHaveTextContent('OUTCOME: target moved')
    expect(screen.getByTestId('edit-outcome')).toHaveTextContent('fixed 1/1')
  })
})

describe('CapDiff', () => {
  const renderDiff = () =>
    render(
      <QueryClientProvider client={new QueryClient()}>
        <CapDiff runId="r" graph={graph} />
      </QueryClientProvider>,
    )
  it('requests the chosen base and styles inherited / reverted / new distinctly', async () => {
    const spy = vi.spyOn(api, 'capdiff').mockImplementation(async (_r, _t, base) => (base === 'ancestry' ? fx.capdiff_ancestry : fx.capdiff_merge) as never)
    const { container } = renderDiff()
    // newest candidate first: cand_6, the merge
    await screen.findByText('Escalate when unsure.')
    expect(spy.mock.calls[0].slice(1, 3)).toEqual(['cand_6', 'parent'])
    const cls = (k: string) => container.querySelector(`[data-class="${k}"]`) as HTMLElement
    expect(cls('inherited')).toBeTruthy()
    expect(cls('new')).toHaveClass('border-solid')
    expect(cls('reverted')).toHaveClass('border-dotted')
    expect(cls('inherited')).toHaveClass('border-dashed')
    // merge parents are offered as bases
    expect(within(screen.getByLabelText('compare against')).getByText('merge parent cand_3')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('compare against'), { target: { value: 'ancestry' } })
    await screen.findByText(/Who introduced each line/)
    expect(spy.mock.calls.at(-1)?.[2]).toBe('ancestry')
    spy.mockRestore()
  })
})
