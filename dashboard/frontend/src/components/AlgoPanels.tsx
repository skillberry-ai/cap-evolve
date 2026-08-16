/**
 * Per-algorithm additions. Same shell, same visual language, same tokens as every
 * generic panel — these are *additions behind a capability check*, not forks.
 *
 * Each panel renders only the signals its algorithm actually emitted. If a signal is
 * absent the panel is not mounted at all (see `capabilities` in the reducer), so
 * nothing here ever has to invent a placeholder.
 */
import type { AlgoExtra, GraphNode, RunSummaryDetail } from '../lib/types'
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
export function EvographPanel({ extra }: { extra: AlgoExtra }) {
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
                  {finalTest.cost_usd != null ? usd(finalTest.cost_usd) : '—'}
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

/* ------------------------------------------------------------- free-form ---- */

/**
 * Free-form (agent-driven) runs — agent-optimize and evograph. There is no
 * deterministic schedule, so the "iteration" column is a commit order, not a plan, and
 * a round may evaluate only a task subset. Saying that plainly is the whole panel.
 */
export function FreeformPanel({
  summary,
  nodes,
}: {
  summary: RunSummaryDetail
  nodes: GraphNode[]
}) {
  const rounds = nodes.filter((n) => n.id !== 'seed')
  const valTasks = summary.splits?.val ?? summary.tasks?.length ?? null

  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          This run was <strong>agent-driven</strong>: no fixed loop decided what to try
          next. Rows below are commits in the order the agent made them, and each is gated
          against the run's best-at-the-time on val — the same honest bar the
          deterministic loops use.
        </p>
      </Card>
      {rounds.length === 0 ? (
        <Card>
          <div className="px-4 py-10 text-center text-sm text-muted">
            No candidate has been committed yet — the baseline is scored and the loop is
            the agent's to drive. Rows appear as the agent commits edits with{' '}
            <code className="text-foreground">cap-evolve gate-check</code>, and the run
            ends with <code className="text-foreground">cap-evolve finalize</code>.
          </div>
        </Card>
      ) : (
      <Panel title={`Round log — ${rounds.length} commit(s)`}>
        <table className="w-full text-left text-[12px]">
          <thead className="eyebrow border-b border-border">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">candidate</th>
              <th className="px-3 py-2">verdict</th>
              <th className="px-3 py-2 text-right">val</th>
              <th className="px-3 py-2 text-right">tasks scored</th>
              <th className="px-3 py-2 text-right">opt time</th>
              <th className="px-3 py-2">note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rounds.map((n) => {
              const scored = Object.keys(n.per_task ?? {}).length
              const subset = valTasks != null && scored > 0 && scored < valTasks
              return (
                <tr key={n.id} className="hover:bg-surface-2">
                  <td className="tnum px-3 py-1.5 text-muted">{n.iteration ?? '—'}</td>
                  <td className="px-3 py-1.5 font-mono">{n.id}</td>
                  <td className="px-3 py-1.5">
                    <VerdictBadge verdict={n.status} />
                  </td>
                  <td className="tnum px-3 py-1.5 text-right">
                    {n.val == null ? '—' : pct(n.val)}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right">
                    {scored || '—'}
                    {valTasks != null && <span className="text-muted"> / {valTasks}</span>}
                    {subset && (
                      <span
                        className="ml-1 text-indecisive"
                        title="Only a subset of val was scored — the mean covers those tasks only."
                      >
                        subset
                      </span>
                    )}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {duration(n.optimizer_seconds)}
                  </td>
                  <td className="min-w-[240px] px-3 py-1.5 leading-relaxed text-muted">
                    {n.reason || '—'}
                    <TaskMovement fixed={n.fixed} broke={n.broke} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Panel>
      )}
    </div>
  )
}

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

/* --------------------------------------------------- agent-optimize screens ---- */

/**
 * agent-optimize's tiered cheap screens. A screen is a PAIRED eval on a small subset,
 * run before paying for full val: it decides whether the candidate is worth the money.
 *
 * The point of showing it is the disagreement. A screen that promotes on a 3-task subset
 * and then loses on full val is not a contradiction — it is the screen's variance being
 * visible, and `inconclusive` says the subset could not separate the two at all. The
 * subset ids, holdout, and fixed/regressed lists are read from the run's own
 * `screens/*.json`; a number the screen did not record renders "—".
 */
export function ScreensPanel({
  screens,
  nodes,
}: {
  screens: NonNullable<AlgoExtra['screens']>
  nodes: GraphNode[]
}) {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  return (
    <div className="space-y-4">
      <Card className="p-3.5">
        <p className="text-[12px] leading-relaxed text-muted-strong">
          Before paying for a full val eval, agent-optimize runs a <strong>cheap screen</strong>
          : a paired comparison on a small subset of val, split into an{' '}
          <strong>informative</strong> part (tasks the parent already fails or that
          discriminate) and a <strong>holdout</strong> part (tasks the parent passes, to
          catch regressions). The subset mean is a <em>screening</em> statistic — it is
          never the candidate's val score, and a screen that promotes can still lose on
          full val.
        </p>
      </Card>

      <Panel title={`Cheap screens — ${screens.length}`}>
        <table className="w-full min-w-[860px] text-left text-[12px]">
          <thead className="eyebrow border-b border-border">
            <tr>
              <th className="px-3 py-2">candidate</th>
              <th className="px-3 py-2 text-right">tier</th>
              <th className="px-3 py-2">decision</th>
              <th className="px-3 py-2 text-right">subset Δ̄</th>
              <th className="px-3 py-2 text-right">SE</th>
              <th className="px-3 py-2 text-right">n / pool</th>
              <th className="px-3 py-2">subset (holdout · informative)</th>
              <th className="px-3 py-2 text-right">then full val</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {screens.map((s, i) => {
              const node = byId.get(s.candidate)
              const agreed =
                node?.val == null || s.mean_delta == null
                  ? null
                  : (s.mean_delta > 0) === (node.status === 'accepted')
              return (
                <tr key={`${s.screen_tag}-${i}`} className="hover:bg-surface-2">
                  <td className="px-3 py-1.5 font-mono">{s.candidate}</td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">{s.tier ?? '—'}</td>
                  <td className="px-3 py-1.5">
                    <span
                      className={cn(
                        'rounded border px-1.5 py-0.5 text-[11px] font-medium',
                        s.inconclusive
                          ? 'border-indecisive/50 text-indecisive'
                          : s.decision === 'promote'
                            ? 'border-accepted/50 text-accepted'
                            : 'border-rejected/50 text-rejected',
                      )}
                      title={
                        s.inconclusive
                          ? 'The subset could not separate parent from child — promoted on insufficient evidence, not on a measured win.'
                          : undefined
                      }
                    >
                      {s.decision ?? '—'}
                      {s.inconclusive && ' · inconclusive'}
                    </span>
                  </td>
                  <td className="tnum px-3 py-1.5 text-right">
                    {s.mean_delta == null
                      ? '—'
                      : `${s.mean_delta > 0 ? '+' : ''}${s.mean_delta.toFixed(4)}`}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {s.se == null ? '—' : `±${s.se.toFixed(4)}`}
                  </td>
                  <td className="tnum px-3 py-1.5 text-right text-muted">
                    {s.n ?? '—'}
                    {s.pool_n != null && <span> / {s.pool_n}</span>}
                  </td>
                  <td className="tnum px-3 py-1.5 text-[11px]">
                    {s.holdout.length > 0 && (
                      <span className="text-muted">holdout {s.holdout.join(' ')}</span>
                    )}
                    {s.holdout.length > 0 && s.informative.length > 0 && ' · '}
                    {s.informative.length > 0 && (
                      <span className="text-muted-strong">info {s.informative.join(' ')}</span>
                    )}
                    {s.holdout.length === 0 && s.informative.length === 0 && (
                      <span className="text-muted">{s.ids.join(' ') || '—'}</span>
                    )}
                    <TaskMovement fixed={s.fixed} broke={s.regressed} />
                  </td>
                  <td className="tnum px-3 py-1.5 text-right">
                    {node?.val == null ? (
                      <span className="text-muted" title="No full val eval was recorded for this tag.">
                        —
                      </span>
                    ) : (
                      <>
                        {pct(node.val)}{' '}
                        {agreed === false && (
                          <span
                            className="text-accent"
                            title="The screen and the full val eval disagreed — the subset did not reproduce."
                          >
                            ≠ screen
                          </span>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="border-t border-border px-3.5 py-2 text-[11px] text-muted">
          A <span className="text-accent">≠ screen</span> row is the screen failing to
          predict full val. Screens save rollouts; they do not decide acceptance — only
          the val significance gate does.
        </p>
      </Panel>
    </div>
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
