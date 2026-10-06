import { AlertTriangle } from 'lucide-react'
import type { GateDecision, GraphNode, RunSummaryDetail } from '../lib/types'
import { cn } from '../lib/cn'
import { VERDICT } from '../lib/verdict'
import { VerdictBadge } from './StatusBadge'
import { Card } from './ui/Card'

const num = (v: number | null | undefined, digits = 4, sign = false) =>
  v == null ? '—' : `${sign && v > 0 ? '+' : ''}${v.toFixed(digits)}`

const deltaTone = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v > 0 ? 'text-accepted' : v < 0 ? 'text-rejected' : ''

/**
 * Every acceptance decision the gate made, with the uncertainty next to the mean.
 *
 * A bare Δ with no SE and no n is the sloppiness this project exists to avoid, so each
 * row shows Δ̄, SE, n and the bar (k·SE) it was compared against, the Δ against the
 * round's null controls (the noise floor), whether that verdict held across every
 * control replicate, and whether the driver overrode the raw gate — plus the gate's own
 * verbatim reason. A statistic the gate did not record renders "—", never 0.
 */
/**
 * The gate table, rebuilt from the candidate graph when the event-derived
 * `gate_decisions` are missing.
 *
 * `gate_decisions` come from `events.jsonl`. A run dir that no longer ships its event
 * stream (the committed `run_full` static export) would otherwise render "No gate decision
 * recorded yet" over a finished run whose verdicts and parent vals sit on the graph nodes.
 * The numbers are read from the structured `gate_*` fields the reducer copies onto each
 * node — never regexed out of the reason prose (#612). A number the node does not carry
 * stays null; the verbatim reason is still shown below the table.
 */
export function gateRowsFromNodes(nodes: GraphNode[]): GateDecision[] {
  const val = new Map(nodes.map((n) => [n.id, n.val]))
  return nodes
    .filter((n) => n.status !== 'seed' && (n.reason || n.val != null))
    .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
    .map((n) => {
      const pv = n.parent_val ?? (n.parent ? (val.get(n.parent) ?? null) : null)
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
        delta: n.gate_delta ?? (n.val != null && pv != null ? n.val - pv : null),
        stderr: n.gate_stderr ?? null,
        n: n.gate_n ?? null,
        k_se: n.gate_k_se ?? null,
        threshold: n.gate_threshold ?? null,
        resolvable_effect_size: n.gate_resolvable_effect_size,
        gate_mode: n.gate_mode,
        gate_verdict: n.gate_verdict,
        control_relative_verdict: n.control_relative_verdict,
        control_relative_delta: n.control_relative_delta,
        evidence_bar: n.evidence_bar,
        overrode_gate: n.overrode_gate,
        reject_basis: n.reject_basis,
        verdict_stable: n.verdict_stable,
        reason: n.reason ?? '',
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
            <table className="w-full min-w-[1080px] text-left text-[12px]">
              <thead className="eyebrow border-b border-border">
                <tr>
                  <Th>iter</Th>
                  <Th>candidate</Th>
                  <Th>verdict</Th>
                  <Th>
                    <span title="Top: Δ̄ vs the ±k·SE bar. Bottom: Δ vs null controls vs the ±noise floor. Shaded band = inside the bar.">
                      gate (Δ̄ vs k·SE · Δ ctl vs noise)
                    </span>
                  </Th>
                  <Th right>val</Th>
                  <Th right>parent val</Th>
                  <Th right>Δ̄</Th>
                  <Th right>SE</Th>
                  <Th right>n</Th>
                  <Th right>bar (k·SE)</Th>
                  <Th right>Δ vs control</Th>
                  <Th>stability</Th>
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
                    <Td>
                      <GateBar row={r} />
                    </Td>
                    <Td right>{num(r.val, 3)}</Td>
                    <Td right className="text-muted">
                      {num(r.parent_val, 3)}
                    </Td>
                    <Td right className={deltaTone(r.delta)}>
                      {num(r.delta, 4, true)}
                    </Td>
                    <Td right className="text-muted">
                      ±{num(r.stderr)}
                    </Td>
                    <Td right className="text-muted">
                      {r.n ?? '—'}
                    </Td>
                    <Td right className="text-muted">
                      <span
                        title={
                          r.resolvable_effect_size != null
                            ? `resolvable effect size 2·SE = ${r.resolvable_effect_size.toFixed(4)}`
                            : undefined
                        }
                      >
                        {num(r.threshold)}
                      </span>
                      {r.k_se != null && (
                        <span className="ml-1 text-[10px]">k={r.k_se}</span>
                      )}
                    </Td>
                    <Td right className={deltaTone(r.control_relative_delta)}>
                      <span title="Paired Δ against the round's null-control replicates — the noise floor, free of reference drift.">
                        {num(r.control_relative_delta, 4, true)}
                      </span>
                      {r.evidence_bar != null && (
                        <span className="ml-1 text-[10px] text-muted">
                          bar {r.evidence_bar.toFixed(4)}
                        </span>
                      )}
                    </Td>
                    <Td>
                      <span className="flex flex-wrap gap-1">
                        {r.verdict_stable != null && (
                          <span
                            className={cn(
                              'rounded border px-1.5 py-0.5 text-[11px] font-medium',
                              r.verdict_stable
                                ? 'border-accepted/50 text-accepted'
                                : 'border-accent/50 text-accent',
                            )}
                            title={
                              r.verdict_stable
                                ? 'This verdict agreed against EVERY control replicate, not just their pooled average.'
                                : 'Control replicates disagreed with each other — this verdict is not stable.'
                            }
                          >
                            {r.verdict_stable ? 'stable' : 'not stable'}
                          </span>
                        )}
                        {r.overrode_gate === true && (
                          <span
                            className="rounded border border-accent/50 px-1.5 py-0.5 text-[11px] font-medium text-accent"
                            title={`The driver's final verdict overrode the raw gate${r.reject_basis ? ` — basis: ${r.reject_basis}` : ''}.`}
                          >
                            overrode gate{r.gate_verdict ? ` (raw ${r.gate_verdict})` : ''}
                          </span>
                        )}
                        {r.verdict_stable == null && r.overrode_gate !== true && (
                          <span className="text-muted">—</span>
                        )}
                      </span>
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

const BAR_W = 160
const TRACK_H = 9
const VERDICT_FILL: Partial<Record<GateDecision['verdict'], string>> = {
  accept: 'var(--accepted)',
  reject: 'var(--rejected)',
}

/**
 * Δ̄ drawn against the k·SE bar (top track) and the Δ vs null controls drawn against the
 * evidence bar — the noise floor (bottom track), on one zero-centred scale per row. The
 * shaded band is ±bar: a fill that ends inside it did not clear the threshold.
 * ponytail: per-row scale so a +0.003 step stays readable next to a +0.27 one; the
 * numeric columns carry the cross-row comparison.
 */
function GateBar({ row: r }: { row: GateDecision }) {
  if (r.delta == null) return <span className="text-muted">—</span>
  const tracks = [
    { label: 'Δ̄', v: r.delta, bar: r.threshold, barName: 'k·SE' },
    { label: 'Δ ctl', v: r.control_relative_delta, bar: r.evidence_bar, barName: 'noise floor' },
  ].filter((t) => t.v != null) as { label: string; v: number; bar: number | null; barName: string }[]
  const span =
    Math.max(...tracks.flatMap((t) => [Math.abs(t.v), t.bar ?? 0]), 1e-9) * 1.15
  const x = (v: number) => BAR_W / 2 + (v / span) * (BAR_W / 2)
  const fill = VERDICT_FILL[r.verdict] ?? 'var(--indecisive)'
  const h = tracks.length * (TRACK_H + 3)
  const label = tracks
    .map((t) => `${t.label} ${num(t.v, 4, true)}${t.bar != null ? ` vs ${t.barName} ${num(t.bar)}` : ''}`)
    .join('; ')
  return (
    <svg width={BAR_W} height={h} role="img" aria-label={label} className="block">
      <title>{label}</title>
      {tracks.map((t, i) => {
        const y = i * (TRACK_H + 3)
        return (
          <g key={t.label} data-track={t.label}>
            <rect x={0} y={y} width={BAR_W} height={TRACK_H} fill="var(--surface-2)" />
            {t.bar != null && (
              <rect
                data-band
                x={x(-t.bar)}
                y={y}
                width={x(t.bar) - x(-t.bar)}
                height={TRACK_H}
                fill="var(--muted)"
                opacity={0.25}
              />
            )}
            <rect
              data-fill
              x={Math.min(x(0), x(t.v))}
              y={y + 1.5}
              width={Math.max(Math.abs(x(t.v) - x(0)), 1)}
              height={TRACK_H - 3}
              fill={fill}
              opacity={i === 0 ? 1 : 0.6}
            />
            {t.bar != null &&
              [t.bar, -t.bar].map((b) => (
                <line
                  key={b}
                  data-threshold
                  x1={x(b)}
                  x2={x(b)}
                  y1={y - 1}
                  y2={y + TRACK_H + 1}
                  stroke="var(--muted-strong)"
                  strokeWidth={1.5}
                />
              ))}
            <line x1={x(0)} x2={x(0)} y1={y} y2={y + TRACK_H} stroke="var(--border-strong)" />
          </g>
        )
      })}
    </svg>
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
