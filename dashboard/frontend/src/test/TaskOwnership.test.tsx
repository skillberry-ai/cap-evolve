import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TaskOwnership } from '../components/TaskOwnership'
import type { GraphNode } from '../lib/types'

const node = (over: Partial<GraphNode> & { id: string }): GraphNode =>
  ({ parent: null, children: [], status: 'accepted', val: null, ...over }) as GraphNode

describe('TaskOwnership', () => {
  it('renders nothing with fewer than 2 scored candidates', () => {
    const { container } = render(
      <TaskOwnership nodes={[node({ id: 'cand_a', per_task: { t1: 1.0 } })]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders one cell per task and lists each candidate with its ownership count', () => {
    render(
      <TaskOwnership
        nodes={[
          node({ id: 'cand_a', per_task: { t1: 1.0, t2: 0.2 } }),
          node({ id: 'cand_b', per_task: { t1: 0.3, t2: 0.9 } }),
        ]}
      />,
    )
    expect(screen.getByText('Task ownership')).toBeInTheDocument()
    expect(screen.getByText('cand_a')).toBeInTheDocument()
    expect(screen.getAllByText('(1)')).toHaveLength(2) // both own exactly 1 task
  })
})
