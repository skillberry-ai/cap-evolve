import { motion } from 'framer-motion'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle } from 'lucide-react'
import type { Evaluation, RunSummaryDetail } from '../lib/types'
import { compactNum, duration, pct, usd } from '../lib/format'
import { easeEnter, fadeUpItem, staggerContainer } from '../lib/motion'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

const ROLES = [
  { key: 'intake', label: 'Intake', color: 'var(--seed)' },
  { key: 'optimizer', label: 'Optimizer', color: 'var(--accent)' },
  { key: 'runner', label: 'Runner', color: 'var(--accepted)' },
] as const

/** Cost, tokens, and latency split across the three agent roles, plus budget meters
 * that turn amber as soft warnings fire. The optimizer column is real once the loop
 * captures the agent CLI's reported cost. */
export function CostPanel({ summary }: { summary: RunSummaryDetail }) {
  const cost = summary.cost
  const tok = summary.tokens_by_role
  const secs = {
    intake: summary.intake_seconds ?? 0,
    optimizer: summary.optimizer_seconds ?? 0,
    runner: summary.runner_seconds ?? 0,
  }
  const usdByRole: Record<string, number> = {
    intake: cost?.intake_usd ?? 0,
    optimizer: cost?.optimizer_usd ?? 0,
    runner: cost?.runner_usd ?? 0,
  }
  const chartData = ROLES.map((r) => ({ ...r, usd: usdByRole[r.key] }))
  const total = cost?.total_usd ?? 0

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="space-y-4">
      <motion.div variants={fadeUpItem}>
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium">Cost by role</h3>
            <span className="tnum text-sm">
              total <span className="font-semibold text-accent">{usd(total)}</span>
            </span>
          </div>
          {total > 0 ? (
            <div style={{ width: '100%', height: 130 }}>
              <ResponsiveContainer>
                <BarChart layout="vertical" data={chartData} margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
                  <XAxis type="number" stroke="var(--muted)" tick={{ fontSize: 11 }} tickFormatter={(v) => usd(v)} />
                  <YAxis type="category" dataKey="label" stroke="var(--muted)" tick={{ fontSize: 12 }} width={72} />
                  <Tooltip
                    cursor={{ fill: 'var(--surface-2)' }}
                    contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    formatter={(v) => [usd(Number(v)), 'cost']}
                  />
                  <Bar dataKey="usd" radius={[0, 4, 4, 0]} isAnimationActive>
                    {chartData.map((d) => (
                      <Cell key={d.key} fill={d.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted">
              No cost recorded yet. Optimizer cost appears once the agent CLI reports it
              (run with the cost path on).
            </p>
          )}
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            {ROLES.map((r) => (
              <div key={r.key} className="rounded bg-surface-2 px-2 py-2">
                <div className="flex items-center justify-center gap-1.5 text-[11px] uppercase tracking-wide text-muted">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} />
                  {r.label}
                </div>
                <div className="tnum mt-1 text-sm font-semibold">{usd(usdByRole[r.key])}</div>
                <div className="tnum text-[11px] text-muted">
                  {compactNum(tok?.[r.key] ?? null)} tok · {duration(secs[r.key])}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </motion.div>

      <motion.div variants={fadeUpItem}>
        <PerIterationCostTime summary={summary} />
      </motion.div>

      <motion.div variants={fadeUpItem}>
        <EvaluationsTable summary={summary} />
      </motion.div>

      <motion.div variants={fadeUpItem}>
        <BudgetMeters summary={summary} />
      </motion.div>
    </motion.div>
  )
}

/** Per-iteration optimizer vs runner cost + time, plus an explicit intake row.
 * Time is always shown; cost only when a real number is present ("—" otherwise,
 * since RITS runner cost is frequently $0/null). */
function PerIterationCostTime({ summary }: { summary: RunSummaryDetail }) {
  const rows = summary.per_iteration ?? []
  const intake = summary.intake ?? { usd: 0, seconds: 0, tokens: 0 }
  const optMaxSec = Math.max(1e-6, ...rows.map((r) => r.optimizer_seconds))
  const runMaxSec = Math.max(1e-6, ...rows.map((r) => r.runner_seconds))

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium">Optimizer iterations</h3>
        <span className="text-[11px] text-muted">optimizer vs runner · $ when available · time always</span>
      </div>

      {/* Intake row — always shown, even at $0, so it's clear intake spent nothing. */}
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded bg-surface-2 px-3 py-2 text-xs">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--seed)' }} />
          Intake
        </span>
        <span className="tnum text-muted">
          cost <span className="font-semibold text-foreground">{usd(intake.usd)}</span>
          {intake.usd === 0 ? <span className="ml-1 text-muted">(spent $0)</span> : null}
        </span>
        <span className="tnum text-muted">
          time <span className="font-semibold text-foreground">{duration(intake.seconds)}</span>
        </span>
        <span className="tnum text-muted">
          {compactNum(intake.tokens || null)} tok
        </span>
      </div>

      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No iterations recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="py-1.5 pr-2">iter</th>
                <th className="py-1.5 pr-2">candidate</th>
                <th className="py-1.5 pr-2 text-right">opt $</th>
                <th className="py-1.5 pr-2">
                  <span className="inline-flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--accent)' }} />
                    opt time
                  </span>
                </th>
                <th className="py-1.5 pr-2 text-right">run $</th>
                <th className="py-1.5 pr-2">
                  <span className="inline-flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--accepted)' }} />
                    run time
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.candidate} className="border-b border-border/50">
                  <td className="tnum py-1.5 pr-2 text-muted">{r.iteration}</td>
                  <td className="py-1.5 pr-2 font-mono text-[11px]">{r.candidate}</td>
                  <td className="tnum py-1.5 pr-2 text-right">{r.optimizer_usd != null ? usd(r.optimizer_usd) : '—'}</td>
                  <td className="py-1.5 pr-2">
                    <TimeBar seconds={r.optimizer_seconds} max={optMaxSec} color="var(--accent)" />
                  </td>
                  <td className="tnum py-1.5 pr-2 text-right">{r.runner_usd != null ? usd(r.runner_usd) : '—'}</td>
                  <td className="py-1.5 pr-2">
                    <TimeBar seconds={r.runner_seconds} max={runMaxSec} color="var(--accepted)" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

/** A tiny inline bar + label so time is legible per iteration without a full chart. */
function TimeBar({ seconds, max, color }: { seconds: number; max: number; color: string }) {
  const frac = max > 0 ? Math.min(1, seconds / max) : 0
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full" style={{ width: `${frac * 100}%`, background: color }} />
      </div>
      <span className="tnum text-muted">{duration(seconds)}</span>
    </div>
  )
}

const EVAL_BADGE: Record<Evaluation['kind'], { label: string; color: string }> = {
  baseline: { label: 'baseline', color: 'var(--seed)' },
  candidate: { label: 'candidate', color: 'var(--accepted)' },
  test: { label: 'test', color: 'var(--accent)' },
}

/** Eval-centric view (distinct from the optimizer-step table above): the seed
 * baseline on val, every full val eval, and the sealed test eval. Shows reward±stderr,
 * runner spend, and the tasks×trials that produced each number. */
function EvaluationsTable({ summary }: { summary: RunSummaryDetail }) {
  const evals = summary.evaluations ?? []
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium">Evaluations</h3>
        <span className="text-[11px] text-muted">each scoring of a candidate on a split</span>
      </div>
      {evals.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No evaluations recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted">
                <th className="py-1.5 pr-2">kind</th>
                <th className="py-1.5 pr-2">candidate</th>
                <th className="py-1.5 pr-2">split</th>
                <th className="py-1.5 pr-2 text-right">reward ± stderr</th>
                <th className="py-1.5 pr-2 text-right">run $</th>
                <th className="py-1.5 pr-2 text-right">time</th>
                <th className="py-1.5 pr-2 text-right">tokens</th>
                <th className="py-1.5 pr-2 text-right">tasks × trials</th>
              </tr>
            </thead>
            <tbody>
              {evals.map((e) => {
                const badge = EVAL_BADGE[e.kind] ?? EVAL_BADGE.candidate
                return (
                  <tr key={e.id} className="border-b border-border/50">
                    <td className="py-1.5 pr-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: badge.color }} />
                        {badge.label}
                      </span>
                    </td>
                    <td className="py-1.5 pr-2 font-mono text-[11px]">{e.candidate}</td>
                    <td className="py-1.5 pr-2 text-muted">{e.split}</td>
                    <td className="tnum py-1.5 pr-2 text-right">
                      {pct(e.reward)}
                      {e.stderr != null && <span className="text-muted"> ± {(e.stderr * 100).toFixed(1)}%</span>}
                    </td>
                    <td className="tnum py-1.5 pr-2 text-right">{e.cost_usd ? usd(e.cost_usd) : '—'}</td>
                    <td className="tnum py-1.5 pr-2 text-right">{duration(e.seconds)}</td>
                    <td className="tnum py-1.5 pr-2 text-right">{compactNum(e.tokens || null)}</td>
                    <td className="tnum py-1.5 pr-2 text-right">
                      {e.n_tasks} × {e.trials}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function BudgetMeters({ summary }: { summary: RunSummaryDetail }) {
  const b = summary.budget
  const warned = new Set((summary.budget_warnings ?? []).map((w) => w.metric))
  const meters: { label: string; spent: number; limit: number; fmt: (n: number) => string }[] = []
  if (b?.max_usd) meters.push({ label: 'Total spend', spent: summary.cost?.total_usd ?? 0, limit: b.max_usd, fmt: usd })
  if (b?.max_optimizer_usd)
    meters.push({ label: 'Optimizer spend', spent: summary.cost?.optimizer_usd ?? 0, limit: b.max_optimizer_usd, fmt: usd })
  if (b?.max_metric_calls)
    meters.push({
      label: 'Runner evals',
      spent: summary.spent?.metric_calls ?? 0,
      limit: b.max_metric_calls,
      fmt: (n) => compactNum(n) ?? String(n),
    })

  if (meters.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="mb-1 text-sm font-medium">Budget</h3>
        <p className="text-sm text-muted">No hard caps set — set max_usd / max_metric_calls to bound spend.</p>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-medium">Budget usage</h3>
      <div className="space-y-3">
        {meters.map((m) => {
          const frac = m.limit > 0 ? Math.min(1, m.spent / m.limit) : 0
          const tone = frac >= 0.8 ? 'bg-rejected' : frac >= 0.5 ? 'bg-amber-500' : 'bg-accepted'
          return (
            <div key={m.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-muted">{m.label}</span>
                <span className="tnum">
                  {m.fmt(m.spent)} / {m.fmt(m.limit)} ({Math.round(frac * 100)}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                <motion.div
                  className={cn('h-full rounded-full', tone)}
                  initial={{ width: 0 }}
                  animate={{ width: `${frac * 100}%` }}
                  transition={easeEnter}
                />
              </div>
            </div>
          )
        })}
      </div>
      {(summary.budget_warnings?.length ?? 0) > 0 && (
        <div className="mt-3 flex items-start gap-1.5 rounded bg-amber-500/10 px-2 py-1.5 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>
            {summary.budget_warnings!.map((w) => `${w.metric} crossed ${w.pct}%`).join(' · ')}
            {warned.size > 0 ? ' — consider killing the run if this looks wrong.' : ''}
          </span>
        </div>
      )}
    </Card>
  )
}
