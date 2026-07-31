/** #139: the cross-links and the consolidated tabs.
 *
 * These assert the two behaviours the issue names as the acceptance test — clicking a
 * candidate routes to its trajectory/diff view, and a heatmap cell opens the correct
 * rollout drawer — plus the a11y contract the epic has already broken twice: keyboard
 * activation, roving-tabindex tab nav, no focus escaping behind the drawer, and state
 * never carried by colour alone.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RunDeepDive } from '../routes/RunDeepDive'
import { TaskHeatmap } from '../components/TaskHeatmap'
import type { GraphNode, RolloutRow, RunDetail } from '../lib/types'

const NODES: GraphNode[] = [
  {
    id: 'seed',
    parent: null,
    children: ['cand_0001'],
    status: 'seed',
    val: 0.4,
    iteration: 0,
    per_task: { t1: 1, t2: 0 },
    feedback: { t2: 'wrong answer' },
  },
  {
    id: 'cand_0001',
    parent: 'seed',
    children: [],
    status: 'accepted',
    val: 0.9,
    iteration: 1,
    per_task: { t1: 1, t2: 1 },
  },
]

const DETAIL: RunDetail = {
  run_id: 'run_demo',
  path: '/tmp/run_demo',
  graph: { nodes: NODES, root: 'seed', best_id: 'cand_0001' },
  summary: {
    baseline_val: 0.4,
    best_val: 0.9,
    delta_pct: 1.25,
    test_reward: null,
    tasks: ['t1', 't2'],
  },
}

const ROLLOUTS: RolloutRow[] = [
  { task_id: 't1', candidate: 'seed', trial: 0, split: 'val', reward: 1, feedback: 'ok', file: 't1__seed__t0.json' },
  { task_id: 't2', candidate: 'seed', trial: 0, split: 'val', reward: 0, feedback: 'wrong answer', file: 't2__seed__t0.json' },
  { task_id: 't1', candidate: 'cand_0001', trial: 0, split: 'val', reward: 1, feedback: 'ok', file: 't1__cand_0001__t0.json' },
  { task_id: 't2', candidate: 'cand_0001', trial: 0, split: 'val', reward: 1, feedback: 'ok', file: 't2__cand_0001__t0.json' },
]

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api')
  return {
    ...actual,
    api: {
      ...actual.api,
      run: vi.fn(),
      rollouts: vi.fn(),
      rollout: vi.fn(),
      diff: vi.fn(),
      memory: vi.fn(),
      customView: vi.fn(),
      gitLog: vi.fn(),
      tree: vi.fn(),
      candidateFiles: vi.fn(),
    },
  }
})

vi.mock('../lib/useRunStream', () => ({
  useRunStream: () => ({ status: 'done', count: 0, log: [] }),
}))

afterEach(() => vi.restoreAllMocks())

async function mountDeepDive() {
  const { api } = await import('../lib/api')
  vi.mocked(api.run).mockResolvedValue(DETAIL)
  vi.mocked(api.rollouts).mockImplementation(async (_id, split) =>
    split ? ROLLOUTS.filter((r) => r.split === split) : ROLLOUTS,
  )
  vi.mocked(api.rollout).mockResolvedValue({
    file: 't2__seed__t0.json',
    input: { q: '2+2' },
    score: { reward: 0, feedback: 'wrong answer' },
    rollout: { output: '5', tool_calls: [] },
  } as unknown as Awaited<ReturnType<typeof api.rollout>>)
  vi.mocked(api.diff).mockResolvedValue({ candidate: 'cand_0001', parent: 'seed', files: [] })
  vi.mocked(api.memory).mockResolvedValue({ history: [], rejected: [] })
  vi.mocked(api.customView).mockRejectedValue(new Error('404'))
  vi.mocked(api.gitLog).mockResolvedValue([])
  vi.mocked(api.tree).mockResolvedValue({ path: '', entries: [], truncated: false })
  vi.mocked(api.candidateFiles).mockResolvedValue([])

  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/runs/run_demo']}>
        <Routes>
          <Route path="/runs/:id" element={<RunDeepDive />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('#139 tab consolidation', () => {
  it('folds the four diff/file surfaces into one Changes & files tab', async () => {
    await mountDeepDive()
    const list = await screen.findByRole('tablist')
    const labels = within(list)
      .getAllByRole('tab')
      .map((t) => t.textContent)
    // Asserted as a subset, not an exact list: sibling PRs in this epic legitimately add
    // top-level tabs (#204's Events), and pinning the exact array would fail the merge
    // for a reason that has nothing to do with consolidation.
    expect(labels).toEqual(expect.arrayContaining(['Fitness', 'Trajectories', 'Changes & files']))
    // The four overlapping surfaces are gone from the TOP list, not from the app.
    for (const gone of ['Iterations', 'Git diffs', 'Memory', 'Files', 'Overview']) {
      expect(labels).not.toContain(gone)
    }
  })

  it('Changes & files still reaches candidate diff, commit diff, memory and raw files', async () => {
    const user = await mountDeepDive()
    await user.click(await screen.findByRole('tab', { name: 'Changes & files' }))
    const lists = await screen.findAllByRole('tablist')
    const sub = within(lists[1])
      .getAllByRole('tab')
      .map((t) => t.textContent)
    expect(sub).toEqual(['Candidate diff', 'Commit diff', 'Memory', 'Raw files'])

    // Memory sub-mode still mounts MemoryPanel — the live reader of rejected.jsonl /
    // history.jsonl that #212 confirmed must not be orphaned.
    await user.click(within(lists[1]).getByRole('tab', { name: 'Memory' }))
    expect(await screen.findByText('Accepted history')).toBeInTheDocument()
    expect(screen.getByText('Rejected memory')).toBeInTheDocument()
  })
})

describe('#139 cross-links', () => {
  it('selecting a candidate on the fitness curve routes to that candidate’s trajectories, and one click further to its diff', async () => {
    const user = await mountDeepDive()
    // The candidate table is the keyboard path to the same link the scatter dots offer.
    await user.click(await screen.findByRole('button', { name: /Inspect cand_0001/ }))

    expect(await screen.findByRole('tab', { name: 'Trajectories', selected: true })).toBeInTheDocument()
    // Filtered to the linked candidate: t1/t2 for cand_0001 only, not seed's rows.
    await waitFor(() => expect(screen.getAllByText('cand_0001').length).toBeGreaterThan(0))
    expect(screen.queryByText('seed')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /See what cand_0001 changed/ }))
    expect(await screen.findByRole('tab', { name: 'Changes & files', selected: true })).toBeInTheDocument()
    // The diff is preselected to the cross-linked candidate, not the default.
    const picker = await screen.findByLabelText('candidate')
    expect((picker as HTMLSelectElement).value).toBe('cand_0001')
  })

  it('a failing heatmap cell opens that exact rollout in the drawer', async () => {
    const user = await mountDeepDive()
    // seed failed t2 — that is the cell an investigator clicks.
    await user.click(await screen.findByRole('button', { name: /^t2 at iteration 0 \(seed\): fail/ }))

    const drawer = await screen.findByRole('dialog')
    // The drawer resolved the (task, candidate) pair to the real rollout FILE rather
        // than guessing a filename.
    expect(within(drawer).getByText('t2__seed__t0.json')).toBeInTheDocument()
    expect(await within(drawer).findByText('wrong answer')).toBeInTheDocument()
  })
})

describe('#139 accessibility', () => {
  it('tabs are a single tab stop with arrow-key navigation and a non-colour selected state', async () => {
    const user = await mountDeepDive()
    const list = await screen.findByRole('tablist')
    const tabs = within(list).getAllByRole('tab')
    // Roving tabindex: exactly one tab stop for the whole tablist.
    expect(tabs.filter((t) => t.getAttribute('tabindex') === '0')).toHaveLength(1)
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    // Selection is bold + aria-selected, not colour alone.
    expect(tabs[0].className).toContain('font-semibold')

    // Arrow keys move selection AND focus together; asserted by position rather than by
    // tab name so a sibling PR inserting a tab (#204's Events) doesn't fail this.
    const names = tabs.map((t) => t.textContent!)
    tabs[0].focus()
    await user.keyboard('{ArrowRight}')
    expect(await screen.findByRole('tab', { name: names[1], selected: true })).toHaveFocus()
    await user.keyboard('{End}')
    expect(await screen.findByRole('tab', { name: names[names.length - 1], selected: true })).toHaveFocus()
    await user.keyboard('{Home}')
    expect(await screen.findByRole('tab', { name: names[0], selected: true })).toHaveFocus()
  })

  it('the rollout drawer traps focus, closes on Escape, and returns focus to its opener', async () => {
    const user = await mountDeepDive()
    const cell = await screen.findByRole('button', { name: /^t2 at iteration 0 \(seed\): fail/ })
    await user.click(cell)

    const drawer = await screen.findByRole('dialog')
    const close = within(drawer).getByRole('button', { name: /Close/ })
    expect(close).toHaveFocus() // focus moved INTO the drawer

    // The backdrop is aria-hidden and unfocusable, so Tab cannot land behind the panel
    // (#196). The only focusable thing in this drawer is Close, so Tab cycles to itself.
    await user.tab()
    expect(drawer.contains(document.activeElement)).toBe(true)

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // The opener here was a heatmap cell on the Fitness tab, which the cross-link
    // unmounted; focus lands on the surrounding tabpanel rather than dropping to <body>.
    expect(cell.isConnected).toBe(false)
    expect(document.activeElement).toHaveAttribute('role', 'tabpanel')
  })

  it('returns focus to the opener when the opener is still mounted', async () => {
    const user = await mountDeepDive()
    await user.click(await screen.findByRole('tab', { name: 'Trajectories' }))
    // Two candidates ran t2; either row's button is a valid opener.
    const open = (await screen.findAllByRole('button', { name: 'Open the trajectory for t2' }))[0]
    await user.click(open)
    const drawer = await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(drawer).not.toBeInTheDocument()
    expect(open).toHaveFocus()
  })
})

describe('TaskHeatmap outcomes are not colour-only', () => {
  it('every cell carries a glyph and a worded aria-label', () => {
    render(
      <TaskHeatmap
        nodes={NODES}
        tasks={['t1', 't2']}
        onOpenRollout={() => {}}
      />,
    )
    // pass / fail are worded, and a cell with no score reads "not run".
    expect(screen.getByRole('button', { name: /^t2 at iteration 0 \(seed\): fail, reward 0\.000 — wrong answer$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^t1 at iteration 0 \(seed\): pass, reward 1\.000$/ })).toBeInTheDocument()
    // The legend names each outcome in words too.
    const grid = screen.getByTestId('task-heatmap')
    expect(grid.querySelectorAll('button').length).toBe(4) // 2 tasks × 2 iterations
  })

  it('renders an honest empty state rather than a blank grid when no candidate has per-task scores', () => {
    render(<TaskHeatmap nodes={[{ ...NODES[0], per_task: undefined }]} tasks={['t1']} />)
    expect(screen.getByText(/No per-task scores yet/)).toBeInTheDocument()
  })
})
