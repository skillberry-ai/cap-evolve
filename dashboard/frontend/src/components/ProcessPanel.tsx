import { api } from '../lib/api'
import { Card } from './ui/Card'

/** The optimizer's own self-rendered `dashboard.html` snapshot (written mid-run via
 * `cap-evolve dashboard --export`), embedded raw so it renders as the real self-contained
 * document it is -- not re-parsed through this app's own styling. */
export function ProcessPanel({ runId }: { runId: string }) {
  return (
    <Card className="p-0">
      <iframe
        src={api.processHtmlURL(runId)}
        title="Optimizer process snapshot"
        className="h-[80vh] w-full rounded-lg border-0"
        sandbox="allow-scripts"
      />
    </Card>
  )
}
