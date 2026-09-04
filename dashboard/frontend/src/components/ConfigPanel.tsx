import { FileCode, FolderTree } from 'lucide-react'
import type { RunSummaryDetail } from '../lib/types'
import { Card } from './ui/Card'

/** The intake-authored project: capevolve.yaml (grouped), PROJECT.md, and every other
 * file under the project dir (adapters/, seed_capability/, split files). Read-only,
 * generic — a future intake artifact shows up automatically, never needs a new panel. */
export function ConfigPanel({ summary }: { summary: RunSummaryDetail }) {
  const cfg = summary.config
  if (!cfg) {
    return (
      <Card className="p-8 text-center text-sm text-muted">No project config found for this run.</Card>
    )
  }
  return (
    <div className="space-y-4">
      {cfg.spec_missing && (
        <Card className="border-border-strong p-3 text-sm text-muted">
          {cfg.project_dir} has no capevolve.yaml — showing the other project artifacts that are there.
        </Card>
      )}

      {cfg.spec_groups.map((g) => (
        <Card key={g.group} className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
            <FileCode size={15} className="text-primary" /> {g.group}
          </h3>
          <table className="w-full text-xs">
            <tbody>
              {g.items.map((it) => (
                <tr key={it.key} className="border-b border-border/50 last:border-0">
                  <td className="py-1 pr-4 align-top font-mono text-[11px] text-muted">{it.key}</td>
                  <td className="py-1 font-mono text-[11px] text-foreground">
                    {typeof it.value === 'string' ? it.value : JSON.stringify(it.value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}

      {cfg.project_md && (
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-medium">PROJECT.md</h3>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">
            {cfg.project_md}
          </pre>
        </Card>
      )}

      {cfg.files.length > 0 && (
        <Card className="p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
            <FolderTree size={15} className="text-primary" /> Other project files
          </h3>
          <div className="divide-y divide-border">
            {cfg.files.map((f) => (
              <details key={f.path} className="py-1.5">
                <summary className="cursor-pointer font-mono text-xs text-muted hover:text-foreground">
                  {f.path} <span className="tnum text-[10px]">({f.size.toLocaleString()} bytes)</span>
                </summary>
                {f.binary ? (
                  <p className="mt-1 text-xs text-muted">binary file — no preview</p>
                ) : (
                  <pre className="mt-1 max-h-72 overflow-auto rounded bg-background p-2 text-xs">
                    {f.preview}
                    {f.truncated ? '\n…[truncated]' : ''}
                  </pre>
                )}
              </details>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
