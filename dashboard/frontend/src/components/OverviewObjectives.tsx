import { useQuery } from '@tanstack/react-query'
import { api, STATIC_MODE } from '../lib/api'
import type { GraphNode, RunSummaryDetail } from '../lib/types'
import { ParetoScatter, isMultiObjective } from './ParetoScatter'
import { SeriesCharts } from './SeriesCharts'

/** Overview charts fed by GET /api/runs/{id}/objectives. Renders nothing in a static
 *  export (the endpoint is not exported) or when the request fails -- the older
 *  cost_usd-based charts remain. */
export function OverviewObjectives({ runId, nodes, summary }: { runId: string; nodes: GraphNode[]; summary: RunSummaryDetail }) {
  const { data } = useQuery({
    queryKey: ['objectives', runId],
    queryFn: ({ signal }) => api.objectives(runId, signal),
    enabled: !STATIC_MODE,
    retry: false,
  })
  if (!data) return isMultiObjective(summary) ? <ParetoScatter nodes={nodes} /> : null
  return (
    <>
      <SeriesCharts nodes={nodes} objectives={data} />
      {isMultiObjective(summary) && <ParetoScatter nodes={nodes} objectives={data} />}
    </>
  )
}
