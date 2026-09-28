import { useQuery } from '@tanstack/react-query'
import { api, STATIC_MODE } from '../lib/api'
import { Card } from './ui/Card'
import { Skeleton } from './ui/Skeleton'

const FRAME = 'h-[80vh] w-full rounded-lg border-0'

/** The optimizer's own self-rendered `dashboard.html` snapshot (written mid-run via
 * `cap-evolve dashboard --export`), embedded raw so it renders as the real self-contained
 * document it is -- not re-parsed through this app's own styling.
 *
 * Live backend: the iframe loads the /api/* route. Static export: there is no /api/*, so
 * the document is fetched from the export's data dir and handed to the iframe as srcdoc. */
export function ProcessPanel({ runId }: { runId: string }) {
  return (
    <Card className="p-0">
      {STATIC_MODE ? (
        <StaticProcessFrame runId={runId} />
      ) : (
        <iframe
          src={api.processHtmlURL(runId)}
          title="Optimizer process snapshot"
          className={FRAME}
          sandbox="allow-scripts"
        />
      )}
    </Card>
  )
}

function StaticProcessFrame({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['process-html', runId],
    queryFn: ({ signal }) => api.processHtml(runId, signal),
  })
  if (isLoading) return <Skeleton className="h-[80vh] w-full" />
  if (error || data === undefined) {
    return (
      <p className="p-4 text-sm text-muted">
        The process snapshot is not in this export.
      </p>
    )
  }
  return (
    <iframe srcDoc={data} title="Optimizer process snapshot" className={FRAME} sandbox="allow-scripts" />
  )
}
