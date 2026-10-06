/**
 * Per-algorithm additions. Same shell, same visual language, same tokens as every
 * generic panel — these are *additions behind a capability check*, not forks.
 *
 * Each panel renders only the signals its algorithm actually emitted. If a signal is
 * absent the panel is not mounted at all (see `capabilities` in the reducer), so
 * nothing here ever has to invent a placeholder.
 */
import { useState } from 'react'
import type { AlgoExtra, GateDecision, GraphNode, RunSummaryDetail, ScreenRow } from '../lib/types'
import { Card } from './ui/Card'
import { VerdictBadge } from './StatusBadge'
import { duration, pct, usd } from '../lib/format'
import { cn } from '../lib/cn'

/* ------------------------------------------------------------------ GEPA ---- */

/**
 * GEPA's two-stage economics: a cheap minibatch local gate, then — only on pass — the
 * expensive full-val eval behind the significance gate. Showing them in one place is
 * the point: a minibatch score is NOT a val score and must never be read as one.
 */
export function GepaPanel({
  extra,
  nodes,
}: {
  extra: AlgoExtra
  nodes: GraphNode[]
}) {
  const mb = extra.minibatch ?? []
  const events = extra.gepa ?? []
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const selects = events.filter((e) => e.kind === 'gepa_select')
  const localGates = events.filter((e) => e.kind === 'gepa_local_gate')
  const merges = events.filter((e) => e.kind.startsWith('gepa_merge'))

  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          GEPA samples a parent from a <strong>per-instance Pareto frontier</strong>, checks
          the child on a cheap <strong>minibatch</strong> of train tasks, and pays for a
          full val eval only when that local gate passes. The minibatch number is a
          screening statistic on a different split — it is never the candidate's val score.
        </p>
      </Card>

      {mb.length > 0 && (
        <Panel title="Minibatch screening vs full val">
          <table className="w-full text-left text-[12px]">
            <thead className="eyebrow border-b border-border">
              <tr>
                {/* gepa probes the PARENT and the CHILD on the same minibatch, so a row
                    is a probe tag (mb_p_* / mb_c_*), not always a gated candidate. */}
                <th className="px-3 py-2">minibatch tag</th>
                <th className="px-3 py-2 text-right">minibatch reward</th>
                <th className="px-3 py-2 text-right">n tasks</th>
                <th className="px-3 py-2 text-right">full val</th>
                <th className="px-3 py-2">gate verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {mb.map((m, i) => {
                const node = m.candidate ? byId.get(m.candidate) : undefined
                return (
                  <tr key={`${m.candidate}-${i}`}>
                    <td className="tnum px-3 py-1.5 font-mono">{m.candidate ?? '—'}</td>
                    <td className="tnum px-3 py-1.5 text-right text-primary">
                      {m.reward == null ? '—' : pct(m.reward)}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right text-muted">
                      {m.n_tasks ?? (m.tasks.length || '—')}
                    </td>
                    <td className="tnum px-3 py-1.5 text-right">
                      {node?.val == null ? (
                        <span
                          className="text-muted"
                          title="Never reached a full val eval — the local gate stopped it, so no val score exists."
                        >
                          — not paid for
                        </span>
                      ) : (
                        pct(node.val)
                      )}
                    </td>
                    <td className="px-3 py-1.5">
                      {node ? <VerdictBadge verdict={node.status} /> : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Panel>
      )}

      {selects.length > 0 && (
        <Panel title="Pareto parent selection">
          <EventRows rows={selects} />
        </Panel>
      )}
      {localGates.length > 0 && (
        <Panel title="Local (minibatch) gate decisions">
          <EventRows rows={localGates} />
        </Panel>
      )}
      {merges.length > 0 && (
        <Panel title="System-aware merges across lineages">
          <EventRows rows={merges} />
        </Panel>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- SkillOpt ---- */

/**
 * SkillOpt's schedule: epochs × mini-batches with a textual learning rate (an integer
 * edit budget that decays), plus the gated epoch-boundary slow/meta update.
 */
export function SkillOptPanel({
  extra,
  nodes,
}: {
  extra: AlgoExtra
  nodes: GraphNode[]
}) {
  const events = extra.skillopt ?? []
  const epochs = extra.epochs ?? []
  const start = events.find((e) => e.kind === 'skillopt_start')
  const slow = events.filter((e) => e.kind.startsWith('skillopt_slow'))
  const lrSeries = events
    .map((e) => ({ epoch: e.epoch ?? null, lr: e.lr ?? (e.detail.lr as number | undefined) ?? null }))
    .filter((p) => p.lr != null)

  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          SkillOpt runs a single lineage over <strong>epochs × mini-batches</strong> with a
          textual learning rate — an integer edit budget that decays on the configured
          schedule — and consolidates longitudinal regressions in a gated{' '}
          <strong>slow/meta update</strong> at each epoch boundary.
        </p>
        {start && (
          <dl className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1 text-[11px]">
            {Object.entries(start.detail).map(([k, v]) => (
              <div key={k}>
                <dt className="eyebrow inline">{k}</dt>{' '}
                <dd className="tnum inline font-medium">{String(v)}</dd>
              </div>
            ))}
          </dl>
        )}
      </Card>

      {epochs.length > 0 && (
        <Panel title="Candidates by epoch">
          <div className="space-y-2 p-3.5">
            {epochs.map((ep) => {
              const members = nodes.filter((n) => n.epoch === ep)
              return (
                <div key={ep} className="flex flex-wrap items-center gap-2">
                  <span className="eyebrow w-[70px]">epoch {ep}</span>
                  {members.length === 0 && <span className="text-[12px] text-muted">—</span>}
                  {members.map((n) => (
                    <span
                      key={n.id}
                      className="inline-flex items-center gap-1.5 rounded border border-border
                                 bg-surface-2 px-1.5 py-0.5 text-[11px]"
                    >
                      <span className="font-mono">{n.id}</span>
                      <span className="tnum text-muted">{n.val == null ? '—' : pct(n.val)}</span>
                      <VerdictBadge verdict={n.status} />
                    </span>
                  ))}
                </div>
              )
            })}
          </div>
        </Panel>
      )}

      {lrSeries.length > 0 && (
        <Panel title="Textual learning-rate schedule">
          <div className="flex items-end gap-1.5 p-3.5">
            {lrSeries.map((p, i) => {
              const max = Math.max(...lrSeries.map((x) => x.lr ?? 0), 1)
              return (
                <div key={i} className="flex flex-col items-center gap-1">
                  <div
                    className="w-5 rounded-t bg-primary"
                    style={{ height: `${Math.max(4, ((p.lr ?? 0) / max) * 72)}px` }}
                    title={`lr ${p.lr}`}
                  />
                  <span className="tnum text-[10px] text-muted">{p.lr}</span>
                </div>
              )
            })}
          </div>
        </Panel>
      )}

      {slow.length > 0 && (
        <Panel title="Epoch-boundary slow / meta updates">
          <EventRows rows={slow} />
        </Panel>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- evograph ---- */

const WEAKNESS_TONE: Record<string, string> = {
  solved: 'text-accepted border-accepted/50',
  completed: 'text-accepted border-accepted/40',
  'in-progress': 'text-primary border-primary/50',
  open: 'text-accent border-accent/50',
  reverted: 'text-rejected border-rejected/50',
}

/**
 * evograph's weakness graph, read straight out of the run dir's own `wiki/`.
 *
 * This replaces the embedded iframe that used to require a second server on a second
 * port: the wiki files ARE the contract, so the one dashboard reads them directly and
 * the panel works identically in the live server and the static export.
 */
export function EvographPanel({ extra, metered = true }: { extra: AlgoExtra; metered?: boolean }) {
  const eg = extra.evograph
  if (!eg) return null
  const { rounds, weaknesses } = eg
  const trainRounds = rounds.filter((r) => r.split !== 'test')
  const finalTest = rounds.find((r) => r.split === 'test')
  const primaryOf = (r: (typeof rounds)[number]) =>
    r.primary_metric ? r.metrics[r.primary_metric] : null
  const max = Math.max(...trainRounds.map((r) => primaryOf(r) ?? 0), 1)

  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          evograph is agent-driven: each <strong>round</strong> evaluates the whole train
          split, builds a graph of <strong>weaknesses</strong> (recurring failure
          patterns), dispatches one solver per weakness in its own worktree, and merges
          only improvements. Read from the run dir's <code>wiki/</code> — no second server.
        </p>
      </Card>

      {trainRounds.length > 0 && (
        <Panel title="Primary metric over rounds">
          <div className="flex items-end gap-3 p-3.5">
            {trainRounds.map((r) => (
              <div key={String(r.round)} className="flex flex-1 flex-col items-center gap-1.5">
                <span className="tnum text-[11px] font-semibold">
                  {primaryOf(r) == null ? '—' : pct(primaryOf(r))}
                </span>
                <div
                  className="w-full max-w-[64px] rounded-t bg-primary"
                  style={{ height: `${Math.max(4, ((primaryOf(r) ?? 0) / max) * 120)}px` }}
                />
                <span className="eyebrow">round {String(r.round)}</span>
                <span className="tnum text-[10px] text-muted">
                  {r.num_tasks ?? '—'} tasks
                  {r.completed_at == null && (
                    <span className="ml-1 text-accent">· running</span>
                  )}
                </span>
              </div>
            ))}
            {finalTest && (
              <div className="flex flex-1 flex-col items-center gap-1.5 border-l border-border pl-3">
                <span className="tnum text-[11px] font-semibold text-accepted">
                  {pct(primaryOf(finalTest))}
                </span>
                <div
                  className="w-full max-w-[64px] rounded-t bg-accepted"
                  style={{ height: `${Math.max(4, ((primaryOf(finalTest) ?? 0) / max) * 120)}px` }}
                />
                <span className="eyebrow">sealed test</span>
                <span className="tnum text-[10px] text-muted">
                  {metered === false
                    ? 'n/a'
                    : finalTest.cost_usd != null ? usd(finalTest.cost_usd) : '—'}
                </span>
              </div>
            )}
          </div>
          <p className="border-t border-border px-3.5 py-2 text-[11px] text-muted">
            The sealed test is shown apart from the rounds line on purpose — it is scored
            once, on data no round ever touched.
          </p>
        </Panel>
      )}

      {weaknesses.length > 0 && (
        <Panel title={`Weakness graph — ${weaknesses.length} node(s)`}>
          <ul className="divide-y divide-border">
            {weaknesses.map((w) => (
              <li key={w.slug} className="p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[13px] font-medium">{w.slug}</span>
                  <span
                    className={cn(
                      'rounded border px-1.5 py-0.5 text-[11px] font-medium',
                      WEAKNESS_TONE[String(w.status)] ?? 'text-muted border-border',
                    )}
                  >
                    {String(w.status ?? 'unknown')}
                  </span>
                  {(w.tags ?? []).map((t) => (
                    <span key={t} className="rounded bg-surface-2 px-1.5 text-[10px] text-muted">
                      {t}
                    </span>
                  ))}
                  <span className="tnum ml-auto text-[11px] text-muted">
                    {w.num_solutions ?? 0} solution(s)
                  </span>
                </div>
                <dl className="tnum mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted">
                  <span>discovered round {String(w.discovered_in_round ?? '—')}</span>
                  {w.solved_in_round != null && <span>solved round {String(w.solved_in_round)}</span>}
                  {(w.affected_tasks ?? []).length > 0 && (
                    <span>affects {(w.affected_tasks ?? []).join(', ')}</span>
                  )}
                  {(w.related ?? []).length > 0 && (
                    <span>related → {(w.related ?? []).join(', ')}</span>
                  )}
                </dl>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}

/* -------------------------------------------------------- rounds + screens ---- */

/** Which tasks an edit fixed and which it broke. A mean-preserving swap is churn, and
 *  only these lists prove it — so they render next to the note, not behind a hover. */
function TaskMovement({ fixed, broke }: { fixed?: string[]; broke?: string[] }) {
  if (!fixed?.length && !broke?.length) return null
  return (
    <span className="tnum ml-1 whitespace-nowrap text-[11px]">
      {!!fixed?.length && <span className="text-accepted">fixed {fixed.join(' ')}</span>}
      {!!fixed?.length && !!broke?.length && <span className="text-muted"> · </span>}
      {!!broke?.length && <span className="text-rejected">broke {broke.join(' ')}</span>}
    </span>
  )
}

/**
 * Free-form (agent-driven) runs — agent-optimize and evograph. There is no
 * deterministic schedule, so "round" is a commit order, not a plan.
 *
 * This is the ONE place a round's whole decision trail lives: the cheap screen(s) that
 * triaged the edit, the full-val gate's RAW verdict, the drift-controlled
 * control-relative second opinion (when the round measured one), whether that verdict
 * held across every control replicate, and the FINAL decision — with an explicit
 * "overrode the raw gate" callout when the driver's final call disagreed with it. The
 * Rounds tab and the Screens tab used to be separate views cross-linked only by
 * candidate-id string match, which is how a run's entire story — "raw gate said
 * accept, but the drift-controlled comparison said reject, twice, so the driver
 * overrode it" — stayed recoverable only by reading raw JSON.
 */
export function RoundsTimeline({
  summary,
  nodes,
  screens,
}: {
  summary: RunSummaryDetail
  nodes: GraphNode[]
  screens: ScreenRow[]
}) {
  const rounds = nodes
    .filter((n) => n.id !== 'seed')
    .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
  const gateByCand = new Map((summary.gate_decisions ?? []).map((g) => [g.candidate, g]))
  const screensByCand = new Map<string, ScreenRow[]>()
  for (const s of screens) {
    screensByCand.set(s.candidate, [...(screensByCand.get(s.candidate) ?? []), s])
  }
  // The full val split size, so a gate's own `n` (GateDecision.n) can be compared
  // against it — the difference between "this mean is over all of val" and "this mean
  // is over a subset", which a full-coverage-looking round otherwise hides.
  const valTasks = summary.splits?.val ?? summary.tasks?.length ?? null

  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          This run was <strong>agent-driven</strong>: no fixed loop decided what to try
          next. Each round below is one committed edit, in the order the agent made it —
          its cheap screen(s), its full-val gate, and (when the round measured
          null-control replicates) the drift-controlled second opinion the final
          decision actually rests on.
        </p>
      </Card>
      {rounds.length === 0 ? (
        <Card>
          <div className="px-4 py-10 text-center text-sm text-muted">
            No candidate has been committed yet — the baseline is scored and the loop is
            the agent's to drive. Rounds appear as the agent commits edits with{' '}
            <code className="text-foreground">cap-evolve gate-check</code>, and the run
            ends with <code className="text-foreground">cap-evolve finalize</code>.
          </div>
        </Card>
      ) : (
        rounds.map((n) => (
          <RoundCard
            key={n.id}
            node={n}
            gate={gateByCand.get(n.id)}
            screens={screensByCand.get(n.id) ?? []}
            valTasks={valTasks}
          />
        ))
      )}
    </div>
  )
}

function Step({
  label,
  tone,
  children,
}: {
  label: string
  tone?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex gap-3 border-l-2 border-border py-1.5 pl-3">
      <span className={cn('w-[92px] shrink-0 text-[11px] font-medium uppercase tracking-wide', tone ?? 'text-muted')}>
        {label}
      </span>
      <div className="min-w-0 flex-1 text-[12px] leading-relaxed">{children}</div>
    </div>
  )
}

function RoundCard({
  node: n,
  gate,
  screens,
  valTasks,
}: {
  node: GraphNode
  gate?: GateDecision
  screens: ScreenRow[]
  /** The full val split size, to flag a gate's `n` as a subset of it. */
  valTasks?: number | null
}) {
  const [open, setOpen] = useState(false)
  // The final verdict disagreeing with the raw gate is the whole point of surfacing
  // this — never inferred, only shown when the run itself recorded both.
  const overrode = gate?.overrode_gate === true && gate?.gate_verdict != null
    && gate.gate_verdict !== gate.verdict

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3.5 py-2.5">
        <span className="tnum text-[11px] text-muted">#{n.iteration ?? '—'}</span>
        <span className="font-mono text-[13px] font-semibold">{n.id}</span>
        <VerdictBadge verdict={n.status} />
        {overrode && (
          <span
            className="rounded border border-accent/50 px-1.5 py-0.5 text-[11px] font-medium text-accent"
            title="The driver's final decision disagreed with the raw gate verdict — see the Final step below."
          >
            overrode gate
          </span>
        )}
        <span className="ml-auto tnum text-[11px] text-muted">
          {duration(n.optimizer_seconds)}
        </span>
      </div>

      <div className="space-y-1 px-3.5 py-3">
        {/* Handover missing — must be the FIRST thing seen, not a footnote. Generalizes
            to any driver: the reducer sets this off `optimizer_context_warning`, no
            matter which algorithm emitted it. */}
        {n.context_warning && (
          <div className="mb-2 rounded border border-accent/50 bg-accent/[0.06] px-2.5 py-1.5 text-[11px] text-accent">
            optimizer reasoning for this round was NOT captured live — the note shown
            below is reconstructed after the fact ({n.context_warning.what ?? 'handover'}
            : {n.context_warning.error ?? 'empty'}).
          </div>
        )}

        {screens.length > 0 && (
          <Step label="screen">
            <div className="space-y-1">
              {screens.map((s, i) => {
                // Did this screen's promote/kill call agree with what full val later
                // found? A screen that promoted but whose candidate the full-val gate
                // then rejected (or vice versa) is the screen failing to reproduce —
                // the same check the old ScreensPanel made, just re-anchored here.
                const agreed =
                  n.val == null || s.mean_delta == null
                    ? null
                    : (s.mean_delta > 0) === (n.status === 'accepted')
                return (
                  <div key={`${s.screen_tag}-${i}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span
                      className={cn(
                        'rounded border px-1.5 py-0.5 text-[11px] font-medium',
                        s.inconclusive
                          ? 'border-indecisive/50 text-indecisive'
                          : s.decision === 'promote'
                            ? 'border-accepted/50 text-accepted'
                            : 'border-rejected/50 text-rejected',
                      )}
                    >
                      {s.decision ?? '—'}
                      {s.inconclusive && ' · inconclusive'}
                    </span>
                    <span className="tnum text-muted">
                      Δ̄ {s.mean_delta == null ? '—' : `${s.mean_delta > 0 ? '+' : ''}${s.mean_delta.toFixed(4)}`}
                      {s.se != null && ` ± ${s.se.toFixed(4)}`}
                    </span>
                    <span className="tnum text-[11px] text-muted">
                      {s.n ?? '—'}
                      {s.pool_n != null && ` / ${s.pool_n}`} tasks (tier {s.tier ?? '—'})
                    </span>
                    {agreed === false && (
                      <span
                        className="text-[11px] font-medium text-accent"
                        title="The screen and the full val eval disagreed — the subset did not reproduce."
                      >
                        ≠ screen
                      </span>
                    )}
                    <TaskMovement fixed={s.fixed} broke={s.regressed} />
                  </div>
                )
              })}
            </div>
          </Step>
        )}

        {gate && (
          <Step label="full-val gate">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="tnum">
                val {n.val == null ? '—' : pct(n.val)} vs parent{' '}
                {n.parent_val == null ? '—' : pct(n.parent_val)}
              </span>
              <span className="tnum text-muted">
                Δ {gate.delta == null ? '—' : `${gate.delta > 0 ? '+' : ''}${gate.delta.toFixed(4)}`}
                {gate.stderr != null && ` ± ${gate.stderr.toFixed(4)}`}
                {gate.threshold != null && ` (threshold ${gate.threshold.toFixed(4)})`}
              </span>
              {gate.gate_mode && <span className="text-[11px] text-muted">mode: {gate.gate_mode}</span>}
              {gate.n != null && (
                <span className="tnum text-[11px] text-muted">
                  {gate.n}
                  {valTasks != null && <span> / {valTasks}</span>} tasks
                  {valTasks != null && gate.n > 0 && gate.n < valTasks && (
                    <span
                      className="ml-1 text-indecisive"
                      title="Only a subset of val was scored — this mean covers those tasks only."
                    >
                      subset
                    </span>
                  )}
                </span>
              )}
              <span className="rounded border border-line px-1.5 py-0.5 text-[11px] font-medium">
                raw: {gate.gate_verdict ?? gate.verdict}
              </span>
            </div>
          </Step>
        )}

        {gate?.control_relative_verdict != null && (
          <Step label="vs control" tone="text-primary">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="rounded border border-primary/50 px-1.5 py-0.5 text-[11px] font-medium text-primary">
                {gate.control_relative_verdict}
              </span>
              <span className="tnum text-muted">
                Δ {gate.control_relative_delta == null ? '—' :
                  `${gate.control_relative_delta > 0 ? '+' : ''}${gate.control_relative_delta.toFixed(4)}`}
                {gate.evidence_bar != null && ` (evidence bar ${gate.evidence_bar.toFixed(4)})`}
              </span>
              {gate.verdict_stable != null && (
                <span
                  className={cn(
                    'text-[11px] font-medium',
                    gate.verdict_stable ? 'text-accepted' : 'text-accent',
                  )}
                  title={
                    gate.verdict_stable
                      ? 'This verdict agreed against EVERY control replicate, not just their pooled average.'
                      : 'Control replicates disagreed with each other — this verdict is not stable.'
                  }
                >
                  {gate.verdict_stable ? 'stable' : 'not stable'}
                </span>
              )}
            </div>
          </Step>
        )}

        <Step label="final" tone={overrode ? 'text-accent' : 'text-muted'}>
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <VerdictBadge verdict={n.status} />
            {overrode && (
              <span className="text-accent">
                raw gate said <span className="font-medium">{gate?.gate_verdict}</span>,
                overridden to <span className="font-medium">{gate?.verdict}</span>
                {gate?.reject_basis && <> — basis: <span className="font-mono">{gate.reject_basis}</span></>}
              </span>
            )}
            <TaskMovement fixed={n.fixed} broke={n.broke} />
          </div>
        </Step>

        {(n.reason || gate?.reason) && (
          <div className="mt-1.5 pl-3">
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              className="text-[11px] text-muted underline hover:text-foreground"
            >
              {open ? 'hide note' : 'show note'}
            </button>
            {open && (
              <p className="mt-1 max-w-[900px] whitespace-pre-wrap text-[11px] leading-relaxed text-muted-strong">
                {n.reason || gate?.reason}
              </p>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}

/* ---------------------------------------------------------------- shared ---- */

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <h3 className="border-b border-border px-3.5 py-2.5 text-[13px] font-semibold">{title}</h3>
      <div className="scroll-x">{children}</div>
    </Card>
  )
}

function EventRows({
  rows,
}: {
  rows: { kind: string; t: number | null; candidate: string | null; detail: Record<string, unknown> }[]
}) {
  return (
    <ul className="divide-y divide-border">
      {rows.map((e, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3.5 py-2 text-[11px]">
          <span className="font-mono font-semibold text-primary">{e.kind}</span>
          {e.candidate && <span className="font-mono text-muted-strong">{e.candidate}</span>}
          {Object.entries(e.detail)
            .filter(([k]) => k !== 'candidate' && k !== 'candidate_id')
            .map(([k, v]) => (
              <span key={k} className="tnum text-muted">
                {k}=
                <span className="text-muted-strong">
                  {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
                </span>
              </span>
            ))}
        </li>
      ))}
    </ul>
  )
}
