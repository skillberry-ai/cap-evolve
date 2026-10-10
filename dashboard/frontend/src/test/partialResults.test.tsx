/** #729 review: partial results never pass as full ones; lineage reads parents[]. */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { layoutLineage } from '../lib/lineage'
import { cumulativeBest } from '../lib/bestCurve'
import { BestCurveChart } from '../components/BestCurveChart'
import { KpiStrip } from '../components/KpiStrip'
import { CandidatesPanel } from '../components/CandidatesPanel'
import { LineageTree } from '../components/LineageTree'
import { CapDiff } from '../components/CapDiff'
import { api } from '../lib/api'
import type { GraphNode, RunGraph, RunSummaryDetail } from '../lib/types'

const mk = (over: Partial<GraphNode>): GraphNode =>
  ({ id: 'x', parent: null, children: [], status: 'rejected', val: 0.5, ...over }) as GraphNode
const seedN = mk({ id: 'seed', status: 'seed', val: 0.59, iteration: 0 })
const c1 = mk({ id: 'cand_1', parent: 'seed', parents: ['seed'], status: 'accepted', val: 0.62, iteration: 1 })
// backend artifact: parent == self, parents[] is the truth
const c4 = mk({ id: 'cand_4', parent: 'cand_4', parents: ['cand_1'], status: 'accepted', val: 0.63, iteration: 2 })
const c7 = mk({ id: 'cand_7', parent: 'cand_4', parents: ['cand_4'], status: 'accepted', val: 0.567, iteration: 3 })
const c9 = mk({ id: 'cand_9', parent: 'cand_4', parents: ['cand_4'], val: 0.567, iteration: 4, eval_state: 'screened', coverage: { n_tasks: 8, n_val_tasks: 30 } })
const g: RunGraph = { root: 'seed', best_id: 'cand_7', nodes: [seedN, c1, c4, c7, c9] }

describe('partial results', () => {
  it('spine follows parents[] and ignores a self-parent', () => {
    const lay = layoutLineage(g)
    expect(lay.nodes.find((n) => n.id === 'cand_4')?.parent).toBe('cand_1')
    expect(lay.edges.find((e) => e.to === 'cand_4')).toMatchObject({ from: 'cand_1' })
    expect(lay.nodes.filter((n) => n.onSpine).map((n) => n.id).sort()).toEqual(['cand_1', 'cand_4', 'cand_7', 'seed'])
  })

  it('curve: subset points are off the line by default, badged when included, star on best_id', () => {
    const off = cumulativeBest(g.nodes, 'cand_7')
    expect(off.map((p) => p.id)).not.toContain('cand_9')
    expect(off.find((p) => p.isChampion)?.id).toBe('cand_7')
    const p9 = cumulativeBest(g.nodes, 'cand_7', true).find((p) => p.id === 'cand_9')!
    expect(p9.badge).toBe('8/30 screened')
    expect(p9.isRecord).toBe(false)
    const { container } = render(<BestCurveChart nodes={g.nodes} bestId="cand_7" />)
    expect(screen.getByText(/include 1 screened/)).toBeInTheDocument()
    expect(container).toHaveTextContent('champion cand_7 56.7%')
    expect(container).toHaveTextContent('best seen cand_4 63.0%')
  })

  it('KPI pairs the champion with its own val and shows best-seen separately', () => {
    const s = { best_id: 'cand_7', best_val: 0.63, baseline_val: 0.59, counts: { accepted: 3, rejected: 1, failed: 0, seed: 1, total: 5 } } as unknown as RunSummaryDetail
    render(<KpiStrip summary={s} nodes={g.nodes} />)
    expect(screen.getByText('champion')).toBeInTheDocument()
    expect(screen.getByText('best val seen')).toBeInTheDocument()
    expect(screen.getByText('candidate cand_7')).toBeInTheDocument()
    expect(screen.getByText('candidate cand_4')).toBeInTheDocument()
  })

  it('Candidates table: coverage badge on subset val, parent from parents[]', () => {
    render(<CandidatesPanel graph={g} summary={{ best_id: 'cand_7' } as RunSummaryDetail} />)
    expect(screen.getByText('cand_9', { selector: 'span.font-mono' }).closest('tr')).toHaveTextContent('8/30 screened')
    const r4 = screen.getByText('cand_4', { selector: 'span.font-mono' }).closest('tr')!
    expect(r4.children[3]).toHaveTextContent('cand_1')
  })

  it('lineage nodes carry a non-colour verdict glyph and a from-parent label', () => {
    render(<LineageTree graph={g} />)
    expect(screen.getAllByTestId('verdict-glyph').map((e) => e.textContent)).toContain('✓')
    expect(screen.getAllByTestId('edge-label').some((e) => e.textContent === 'from #4')).toBe(true)
  })

  it('CapDiff hides optimizer bookkeeping files', async () => {
    const files = [
      { path: 'DIAGNOSIS.json', added: 1, removed: 0, rows: [{ t: 'add', l: 'bookkeeping' }] },
      { path: 'SKILL.md', added: 1, removed: 0, rows: [{ t: 'add', l: 'capability line' }] },
    ]
    const spy = vi.spyOn(api, 'capdiff').mockResolvedValue({ target: 'cand_7', mode: 'parent', base: 'cand_4', files } as never)
    render(<QueryClientProvider client={new QueryClient()}><CapDiff runId="r" graph={g} /></QueryClientProvider>)
    await screen.findByText('capability line')
    expect(screen.queryByText('bookkeeping')).toBeNull()
    spy.mockRestore()
  })
})
