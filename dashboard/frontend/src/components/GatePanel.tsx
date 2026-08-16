import { AlertTriangle } from 'lucide-react'
import type { GateDecision, GraphNode, RunSummaryDetail } from '../lib/types'
import { VERDICT } from '../lib/verdict'
import { VerdictBadge } from './StatusBadge'
import { Card } from './ui/Card'

const num = (v: number | null | undefined, digits = 4, sign = false) =>
  v == null ? '—' : `${sign && v > 0 ? '+' : ''}${v.toFixed(digits)}`

/**
 * Every acceptance decision the gate made, with the uncertainty next to the mean.
 *
 * A bare Δ with no SE and no n is the sloppiness this project exists to avoid, so each
 * row shows Δ̄, SE, n and the bar (k·SE) it was compared against, plus the gate's own
 * verbatim reason. A statistic the gate did not record renders "—", never 0.
 */
/**
 * The gate table, rebuilt from the candidate graph when the event-derived
 * `gate_decisions` are missing.
 *
 * `gate_decisions` come from `events.jsonl`. A run dir that no longer ships its event
 * stream (the committed `run_full` static export) therefore rendered "No gate decision
 * recorded yet" over a finished run whose every verdict, val, parent val and verbatim
 * gate reason sit right there on the graph nodes — the Candidates tab printed the
 * arithmetic that this tab claimed did not exist. Δ̄, SE, n and the bar are read back out
 * of the gate's own reason string with the SAME patterns the backend reducer uses
 * (`dashboard.py`, "gate decisions"), because that string IS the audit record. A number
 * that is not in the reason stays null — never a fabricated 0.
 */
const g1 = (re: RegExp, s: string) => {
  const m = re.exec(s)
  return m ? Number(m[1]) : null
}

export function gateRowsFromNodes(nodes: GraphNode[]): GateDecision[] {
  const val = new Map(nodes.map((n) => [n.id, n.val]))
  return nodes
    .filter((n) => n.status !== 'seed' && (n.reason || n.val != null))
    .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
    .map((n) => {
      const pv = n.parent_val ?? (n.parent ? (val.get(n.parent) ?? null) : null)
      const reason = n.reason ?? ''
      const bar = /([\d.]+)·SE\s*=\s*(\d*\.?\d+)/.exec(reason)
      const delta = g1(/Δ̄?\s*=\s*([+-]?\d*\.?\d+)/, reason)
      return {
        iteration: n.iteration ?? null,
        candidate: n.id,
        verdict:
          n.status === 'accepted'
            ? 'accept'
            : n.status === 'rejected'
              ? 'reject'
              : n.status === 'indecisive'
                ? 'indecisive'
                : 'no measurement',
        val: n.val,
        parent: n.parent,
        parent_val: pv,
        delta: delta ?? (n.val != null && pv != null ? n.val - pv : null),
        // NOT the `k·SE=` bar that appears earlier in the same sentence.
        stderr: g1(/(?<!·)\bSE\s*=\s*(\d*\.?\d+)/, reason),
        n: g1(/\bn\s*=\s*(\d+)/, reason),
        k_se: bar ? Number(bar[1]) : null,
        threshold: bar ? Number(bar[2]) : null,
        reason,
      } satisfies GateDecision
    })
}

export function GatePanel({
  summary,
  nodes = [],
}: {
  summary: RunSummaryDetail
  nodes?: GraphNode[]
}) {
  const rows: GateDecision[] = summary.gate_decisions?.length
    ? summary.gate_decisions
    : gateRowsFromNodes(nodes)
  const warnings = (summary.gate_warnings ?? []) as {
    reason?: string
    mode?: string
    context?: string
  }[]
  const indecisive = rows.filter((r) => r.verdict === 'indecisive')

  return (
    <div className="space-y-4">
      {warnings.length > 0 && (
        <Card className="border-accent/40 bg-accent/[0.04]">
          <div className="flex gap-2.5 p-3.5">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-accent" aria-hidden />
            <div className="min-w-0 space-y-2">
              <p className="text-sm font-medium text-accent">
                {warnings.length} gate warning{warnings.length > 1 ? 's' : ''}
              </p>
              {warnings.map((w, i) => (
                <p key={i} className="text-[12px] leading-relaxed text-muted-strong">
                  {w.mode && (
                    <span className="mr-1.5 rounded bg-surface-2 px-1 font-mono text-[11px]">
                      {w.mode}
                    </span>
                  )}
                  {w.reason}
                  {w.context && <span className="ml-1 font-mono text-muted">({w.context})</span>}
                </p>
              ))}
            </div>
          </div>
        </Card>
      )}

      {indecisive.length > 0 && (
        <Card className="border-indecisive/40 bg-indecisive/[0.04]">
          <p className="p-3.5 text-[12px] leading-relaxed text-muted-strong">
            <span className="font-medium text-indecisive">
              {indecisive.length} step{indecisive.length > 1 ? 's' : ''} indecisive.
            </span>{' '}
            {VERDICT.indecisive.blurb} These are excluded from the running-best record and
            from the stall counter — treating them as rejections would blame the edit for
            an infrastructure fault.
          </p>
        </Card>
      )}

      {rows.length === 0 ? (
        <Card>
          <div className="px-4 py-12 text-center text-sm text-muted">
            No gate decision recorded in this run dir. The gate runs once a candidate has
            a full val score — always on val, never on train.
          </div>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="scroll-x">
            <table className="w-full min-w-[720px] text-left text-[12px]">
              <thead className="eyebrow border-b border-border">
                <tr>
                  <Th>iter</Th>
                  <Th>candidate</Th>
                  <Th>verdict</Th>
                  <Th right>val</Th>
                  <Th right>parent val</Th>
                  <Th right>Δ̄</Th>
                  <Th right>SE</Th>
                  <Th right>n</Th>
                  <Th right>bar (k·SE)</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => (
                  <tr key={r.candidate} className="hover:bg-surface-2">
                    <Td className="tnum text-muted">{r.iteration ?? '—'}</Td>
                    <Td className="font-mono">{r.candidate}</Td>
                    <Td>
                      <VerdictBadge verdict={r.verdict} />
                    </Td>
                    <Td right>{num(r.val, 3)}</Td>
                    <Td right className="text-muted">
                      {num(r.parent_val, 3)}
                    </Td>
                    <Td
                      right
                      className={
                        r.delta == null
                          ? 'text-muted'
                          : r.delta > 0
                            ? 'text-accepted'
                            : r.delta < 0
                              ? 'text-rejected'
                              : ''
                      }
                    >
                      {num(r.delta, 4, true)}
                    </Td>
                    <Td right className="text-muted">
                      ±{num(r.stderr)}
                    </Td>
                    <Td right className="text-muted">
                      {r.n ?? '—'}
                    </Td>
                    <Td right className="text-muted">
                      {num(r.threshold)}
                      {r.k_se != null && (
                        <span className="ml-1 text-[10px]">k={r.k_se}</span>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Only decisions that actually carry a rationale. Rendering a row per
              decision produced one blank line per candidate on every run whose gate
              wrote no reason string — a list of ids and nothing else. */}
          {rows.some((r) => r.reason) && (
            <ul className="divide-y divide-border border-t border-border">
              {rows
                .filter((r) => r.reason)
                .map((r) => (
                  <li key={r.candidate} className="flex gap-2.5 px-3 py-2 text-[11px]">
                    <span className="shrink-0 font-mono text-muted">{r.candidate}</span>
                    <span className="min-w-0 leading-relaxed text-muted-strong">{r.reason}</span>
                  </li>
                ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  )
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-3 py-2 font-semibold ${right ? 'text-right' : ''}`}>{children}</th>
}

function Td({
  children,
  right,
  className = '',
}: {
  children: React.ReactNode
  right?: boolean
  className?: string
}) {
  return (
    <td className={`tnum px-3 py-1.5 ${right ? 'text-right' : ''} ${className}`}>{children}</td>
  )
}
