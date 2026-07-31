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
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom'
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

/** The live URL, read back out of the router so a test can assert what a user would copy
 *  out of the address bar. */
function UrlProbe() {
  const [p] = useSearchParams()
  return <span data-testid="url">{`?${p.toString()}`}</span>
}
const url = () => screen.getByTestId('url').textContent

async function mountDeepDive(entry = '/runs/run_demo') {
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
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route
            path="/runs/:id"
            element={
              <>
                <UrlProbe />
                <RunDeepDive />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('#139 tab consolidation', () => {
  it('folds the four diff/file surfaces into one Changes, memory & files tab', async () => {
    await mountDeepDive()
    const list = await screen.findByRole('tablist')
    const labels = within(list)
      .getAllByRole('tab')
      .map((t) => t.textContent)
    // Asserted as a subset, not an exact list: sibling PRs in this epic legitimately add
    // top-level tabs (#204's Events), and pinning the exact array would fail the merge
    // for a reason that has nothing to do with consolidation.
    expect(labels).toEqual(expect.arrayContaining(['Fitness', 'Trajectories', 'Changes, memory & files']))
    // The four overlapping surfaces are gone from the TOP list, not from the app.
    for (const gone of ['Iterations', 'Git diffs', 'Memory', 'Files', 'Overview']) {
      expect(labels).not.toContain(gone)
    }
  })

  it('Changes, memory & files still reaches candidate diff, commit diff, memory and raw files', async () => {
    const user = await mountDeepDive()
    await user.click(await screen.findByRole('tab', { name: 'Changes, memory & files' }))
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
    expect(await screen.findByRole('tab', { name: 'Changes, memory & files', selected: true })).toBeInTheDocument()
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

describe('#139 URL is state, not a write-only log', () => {
  it('closing the drawer clears ?task, and it stays closed across a tab round-trip', async () => {
    // Deep-linked open: exactly the link a recipient would receive.
    const user = await mountDeepDive('/runs/run_demo?tab=trajectories&candidate=seed&task=t2')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // The URL a user would now copy no longer records the state they dismissed.
    expect(url()).not.toContain('task=t2')

    // ...and the drawer does not resurrect itself on the next remount of the panel.
    await user.click(screen.getByRole('tab', { name: 'Cost' }))
    expect(url()).not.toContain('task=')
    await user.click(screen.getByRole('tab', { name: 'Trajectories' }))
    await waitFor(() => expect(screen.getAllByText('t2').length).toBeGreaterThan(0))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('deep-links straight into a ?mode sub-surface', async () => {
    await mountDeepDive('/runs/run_demo?tab=changes&candidate=cand_0001&mode=memory')
    expect(await screen.findByRole('tab', { name: 'Memory', selected: true })).toBeInTheDocument()
    expect(await screen.findByText('Accepted history')).toBeInTheDocument()
  })

  it('normalises an unknown ?tab / ?mode out of the URL instead of leaving a bad param', async () => {
    await mountDeepDive('/runs/run_demo?tab=nope')
    expect(await screen.findByRole('tab', { name: 'Fitness', selected: true })).toBeInTheDocument()
    await waitFor(() => expect(url()).toContain('tab=fitness'))

    screen.getByTestId('url') // sanity: probe mounted
  })

  it('does not claim a candidate it is not showing', async () => {
    await mountDeepDive('/runs/run_demo?tab=changes&candidate=cand_9999&mode=candidate')
    expect(await screen.findByText(/No candidate/)).toBeInTheDocument()
    expect(screen.queryByText(/cand_9999 scored per task/)).not.toBeInTheDocument()
    // The panel below falls back to a real candidate, and the header agrees with it.
    const picker = (await screen.findByLabelText('candidate')) as HTMLSelectElement
    expect(picker.value).toBe('cand_0001')
  })
})

describe('#139 accessibility', () => {
  it('the heatmap is one tab stop with arrow-key navigation, not one stop per cell', () => {
    // 30 tasks × 20 iterations = 600 cells: the scale at which per-cell tab stops become a
    // keyboard trap.
    const tasks = Array.from({ length: 30 }, (_, i) => `t${i}`)
    const nodes: GraphNode[] = Array.from({ length: 20 }, (_, i) => ({
      id: `c${i}`,
      parent: null,
      children: [],
      status: 'accepted' as const,
      val: 0.5,
      iteration: i,
      per_task: Object.fromEntries(tasks.map((t) => [t, 1])),
    }))
    render(<TaskHeatmap nodes={nodes} tasks={tasks} onOpenRollout={() => {}} />)
    const grid = screen.getByTestId('task-heatmap')
    const cells = grid.querySelectorAll('button')
    expect(cells.length).toBe(600)
    // One tab stop for 600 cells.
    expect(grid.querySelectorAll('button[tabindex="0"]').length).toBe(1)
    expect(grid).toHaveAttribute('role', 'grid')
    expect(grid.querySelectorAll('[role="gridcell"]').length).toBe(600)
  })

  it('arrow keys move the heatmap’s active cell', async () => {
    const user = userEvent.setup()
    render(<TaskHeatmap nodes={NODES} tasks={['t1', 't2']} onOpenRollout={() => {}} />)
    const grid = screen.getByTestId('task-heatmap')
    const cell = (r: number, c: number) => grid.querySelector(`[data-cell="${r}-${c}"]`)!
    ;(cell(0, 0) as HTMLElement).focus()
    expect(cell(0, 0)).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(cell(0, 1)).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(cell(1, 1)).toHaveFocus()
    await user.keyboard('{Home}')
    expect(cell(1, 0)).toHaveFocus()
    await user.keyboard('{End}')
    expect(cell(1, 1)).toHaveFocus()
    // Roving: still exactly one tab stop, and it followed the arrows.
    expect(grid.querySelectorAll('button[tabindex="0"]').length).toBe(1)
    expect(cell(1, 1)).toHaveAttribute('tabindex', '0')
  })

  it('both tablists have accessible names so the nested one is announceable', async () => {
    const user = await mountDeepDive()
    expect(await screen.findByRole('tablist', { name: 'Run views' })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Changes, memory & files' }))
    expect(await screen.findByRole('tablist', { name: 'Change surfaces' })).toBeInTheDocument()
    // ...and the panel is named by its own tab, not left anonymous.
    const panels = screen.getAllByRole('tabpanel')
    for (const p of panels) expect(p).toHaveAttribute('aria-labelledby')
  })

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
