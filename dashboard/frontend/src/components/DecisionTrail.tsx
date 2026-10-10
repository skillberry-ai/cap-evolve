import type { OptimizerDecision } from '../lib/types'
import { usd } from '../lib/format'

/** Decision -> token colour. The decision NAME is always printed too, so colour is never
 *  the only carrier. */
const TONE: Record<string, string> = {
  accept: 'var(--accepted)', promote: 'var(--accepted)', merge: 'var(--accepted)',
  reject: 'var(--rejected)', kill: 'var(--rejected)', stop: 'var(--rejected)',
  propose: 'var(--series-1)', screen: 'var(--indecisive)', grow: 'var(--series-4)',
}

export const evidenceText = (e: Record<string, unknown>) =>
  Object.entries(e).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join('\n')

/** Optimizer decisions (propose/screen/promote/kill/merge/grow/accept/reject/stop) in order,
 *  each with its evidence on hover and its own optimizer spend. */
export function DecisionTrail({ decisions }: { decisions?: OptimizerDecision[] }) {
  if (!decisions || decisions.length === 0) return null
  return (
    <section className="mt-4" aria-label="optimizer decisions">
      <h3 className="mb-2 text-sm font-medium">Optimizer decisions</h3>
      <ol className="space-y-1.5">
        {decisions.map((d, i) => (
          <li key={`${d.id}-${i}`} data-testid="decision" title={evidenceText(d.evidence ?? {}) || undefined}
            className="flex flex-wrap items-baseline gap-x-2 text-xs">
            <span className="rounded border px-1.5 py-0.5 font-medium uppercase tracking-wide"
              style={{ borderColor: TONE[d.decision] ?? 'var(--border-strong)', color: TONE[d.decision] ?? 'var(--muted)' }}>
              {d.decision}
            </span>
            <span className="font-mono">{d.id}</span>
            {d.rationale && <span className="text-muted">{d.rationale}</span>}
            {Object.keys(d.evidence ?? {}).length > 0 && (
              <span className="text-muted-strong">{Object.entries(d.evidence).slice(0, 3).map(([k, v]) => `${k}=${typeof v === 'number' ? +v.toFixed(3) : String(v)}`).join(' ')}</span>
            )}
            {d.optimizer_usd != null && <span className="tnum ml-auto text-muted">{usd(d.optimizer_usd)}</span>}
          </li>
        ))}
      </ol>
    </section>
  )
}
