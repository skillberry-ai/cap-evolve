import { useMemo } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { CostLedger as Ledger, CostRow, RunSummaryDetail } from '../lib/types'
import { compactNum, duration, usd } from '../lib/format'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

const PHASE_ORDER: CostRow['phase'][] = ['intake', 'baseline', 'optimize', 'finalize']

const PHASE_LABEL: Record<CostRow['phase'], string> = {
  intake: 'Intake',
  baseline: 'Baseline',
  optimize: 'Optimize',
  finalize: 'Finalize (sealed test)',
}

const KIND_TONE: Record<CostRow['kind'], string> = {
  intake: 'bg-seed',
  baseline_eval: 'bg-primary',
  candidate_eval: 'bg-accepted',
  optimizer_call: 'bg-accent',
  test_eval: 'bg-indecisive',
}

/**
 * Where every dollar went, phase by phase: intake, the baseline eval, each optimizer
 * call (including the ones whose process exited non-zero — a real run spent $6.01
 * against its own $6.00 cap and still paid for it), each evaluation, and the sealed
 * test. The totals reconcile against the run's authoritative spend accounting, and
 * whatever the events cannot account for is shown as an explicit remainder rather
 * than silently absorbed.
 *
 * A row whose cost was never recorded shows "—". It is never rendered as $0.
 */
export function CostLedger({ summary }: { summary: RunSummaryDetail }) {
  const ledger: Ledger | undefined = summary.cost_ledger
  const rows = ledger?.rows ?? []

  const byPhase = useMemo(() => {
    const groups = new Map<CostRow['phase'], CostRow[]>()
    for (const r of rows) {
      const list = groups.get(r.phase) ?? []
      list.push(r)
      groups.set(r.phase, list)
    }
    return PHASE_ORDER.filter((p) => groups.has(p)).map((p) => ({
      phase: p,
      rows: groups.get(p)!,
      usd: groups.get(p)!.reduce((a, r) => a + (r.usd ?? 0), 0),
      missing: groups.get(p)!.filter((r) => r.usd == null).length,
      seconds: groups.get(p)!.reduce((a, r) => a + (r.seconds ?? 0), 0),
      tokens: groups.get(p)!.reduce((a, r) => a + (r.tokens ?? 0), 0),
    }))
  }, [rows])

  // Two different situations, and conflating them states a falsehood. No `cost_ledger` key
  // at all means this run dir predates the ledger (an older static export) -- it may well
  // have spent plenty, and saying "nothing has been charged" would be simply untrue. An
  // EMPTY ledger is the real "nothing charged yet".
  if (!ledger) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          This run dir records no cost <em>ledger</em> — it predates per-phase cost
          attribution, so spend cannot be broken down by phase here. That is not a claim
          that nothing was spent; any totals this run did record are shown above.
        </div>
      </Card>
    )
  }
  if (rows.length === 0) {
    return (
      <Card>
        <div className="px-4 py-12 text-center text-sm text-muted">
          No spend recorded. Cost rows are built from the run's own <code>evaluate</code>{' '}
          and step events — an empty ledger means nothing has been charged yet.
        </div>
      </Card>
    )
  }

  const total = ledger.total_usd
  const unattributed = ledger.unattributed_usd
  const maxRow = Math.max(...rows.map((r) => r.usd ?? 0), 1e-9)

  return (
    <div className="space-y-4">
      {/* Reconciliation strip — the honest headline: what the events explain vs the
          run's recorded total. */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">total recorded spend</p>
            <p className="tnum mt-1 text-2xl font-semibold text-accent">{usd(total)}</p>
          </div>
          <dl className="tnum flex flex-wrap gap-x-6 gap-y-2 text-[12px]">
            <Stat label="attributed to events">{usd(ledger.attributed_usd)}</Stat>
            <Stat
              label="unattributed"
              tone={Math.abs(unattributed) > 0.0005 ? 'text-accent' : 'text-muted'}
            >
              {usd(unattributed)}
            </Stat>
            <Stat label="rows with no cost recorded">{ledger.rows_missing_cost}</Stat>
          </dl>
        </div>
        {Math.abs(unattributed) > 0.0005 && (
          <p className="mt-3 flex gap-2 rounded-md border border-accent/40 bg-accent/[0.05] p-2.5 text-[12px] leading-relaxed text-muted-strong">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden />
            <span>
              {usd(Math.abs(unattributed))} of recorded spend {unattributed > 0 ? 'is not' : 'is over'}{' '}
              accounted for by the rows below. This happens when a phase records into the
              run's spend accounting without emitting a cost-bearing event (agent-mode
              commits are the common case). Shown rather than hidden — the gap is real.
            </span>
          </p>
        )}
      </Card>

      {/* Phase-grouped ledger. */}
      {byPhase.map((g) => (
        <Card key={g.phase} className="overflow-hidden">
          <div className="flex items-baseline justify-between border-b border-border px-3.5 py-2.5">
            <h3 className="text-[13px] font-semibold">{PHASE_LABEL[g.phase]}</h3>
            <span className="tnum text-[12px] text-muted">
              <span className="font-semibold text-foreground">{usd(g.usd)}</span>
              {g.missing > 0 && <span className="text-accent"> +{g.missing} unrecorded</span>}
              {' · '}
              {duration(g.seconds)}
              {g.tokens > 0 && ` · ${compactNum(g.tokens)} tok`}
            </span>
          </div>
          <table className="w-full text-left text-[12px]">
            <tbody className="divide-y divide-border">
              {g.rows.map((r, i) => (
                <tr key={`${r.kind}-${r.candidate}-${i}`} className="hover:bg-surface-2">
                  <td className="w-full px-3.5 py-2">
                    <div className="flex items-center gap-2">
                      <span
                        aria-hidden
                        className={cn('h-2.5 w-2.5 shrink-0 rounded-sm', KIND_TONE[r.kind])}
                      />
                      <span className="min-w-0 truncate">{r.label}</span>
                    </div>
                    {r.note && (
                      <p className="ml-[18px] mt-0.5 text-[11px] leading-snug text-muted">
                        {r.note}
                      </p>
                    )}
                    {/* Proportional bar: relative share of the single largest row. */}
                    <div className="ml-[18px] mt-1 h-1 w-full max-w-[420px] overflow-hidden rounded-full bg-surface-3">
                      <div
                        className={cn('h-full rounded-full', KIND_TONE[r.kind])}
                        style={{ width: `${((r.usd ?? 0) / maxRow) * 100}%` }}
                      />
                    </div>
                  </td>
                  <td className="tnum whitespace-nowrap px-3.5 py-2 text-right align-top">
                    {r.usd == null ? (
                      <span
                        className="text-muted"
                        title="Cost was never recorded for this row — missing, not zero."
                      >
                        —
                      </span>
                    ) : (
                      usd(r.usd)
                    )}
                  </td>
                  <td className="tnum whitespace-nowrap px-3.5 py-2 text-right align-top text-muted">
                    {duration(r.seconds)}
                  </td>
                  <td className="tnum whitespace-nowrap px-3.5 py-2 text-right align-top text-muted">
                    {r.tokens ? compactNum(r.tokens) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  )
}

function Stat({
  label,
  children,
  tone = 'text-foreground',
}: {
  label: string
  children: React.ReactNode
  tone?: string
}) {
  return (
    <div>
      <dt className="eyebrow">{label}</dt>
      <dd className={cn('mt-0.5 font-semibold', tone)}>{children}</dd>
    </div>
  )
}
