import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { RunTimeline } from '../components/RunTimeline'
import type { RunSummaryDetail, GraphNode } from '../lib/types'
import fixtureData from './fixtures/run_payload.json'

describe('RunTimeline', () => {
  it('renders without crashing with fixture data', () => {
    const onActivityClick = vi.fn()
    render(
      <RunTimeline
        summary={fixtureData.summary as unknown as RunSummaryDetail}
        nodes={fixtureData.graph.nodes as unknown as GraphNode[]}
        onActivityClick={onActivityClick}
      />
    )
    // Component should render without throwing
    expect(document.querySelector('svg')).toBeTruthy()
  })

  it('renders with empty activities', () => {
    const onActivityClick = vi.fn()
    const emptySummary = { ...fixtureData.summary, activities: [] } as unknown as RunSummaryDetail
    render(
      <RunTimeline
        summary={emptySummary}
        nodes={fixtureData.graph.nodes as unknown as GraphNode[]}
        onActivityClick={onActivityClick}
      />
    )
    expect(document.querySelector('svg')).toBeTruthy()
  })
})