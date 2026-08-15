import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import type { RunSummaryDetail } from '../lib/types'
import { compactNum, duration, isMeasured, pct, usd } from '../lib/format'
import { fadeUpItem, staggerContainer } from '../lib/motion'
import { CountUp } from './CountUp'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

/**
 * `pass^1 100.0%` — a k missing from the dict means k > num_trials, so the statistic
 * is UNDEFINED, not 0. Never coerce a missing k to a number, and never invent one:
 * render exactly the ks the backend measured, in numeric order.
 */
export function passKHint(pk: RunSummaryDetail['test_pass_k']): string | undefined {
  if (pk == null || typeof pk !== 'object') return undefined
  const ks = Object.keys(pk)
    // The k must be a real integer AND its value an actual finite measurement: an
    // absent or non-finite pass^k is undefined, not 0, and must not be formatted.
    .filter((k) => Number.isFinite(Number(k)) && isMeasured(pk[k]))
    .sort((a, b) => Number(a) - Number(b))
  if (ks.length === 0) return undefined
  return ks.map((k) => `pass^${Number(k)} ${pct(pk[k])}`).join(' · ')
}

/** ±SE suffix, or nothing when the run recorded no uncertainty. A mean with no SE and
 *  no n is exactly the sloppiness this project exists to avoid — so when SE is missing
 *  we say so rather than implying the number is exact. */
function seHint(value: number | null | undefined, se: number | null | undefined, n?: number | null) {
  if (value == null) return undefined
  if (se == null) return 'no stderr recorded'
  return `± ${se.toFixed(3)}${n ? ` · n=${n}` : ''}`
}

/**
 * Six numbers, each carrying its own uncertainty or breakdown. No card restates
 * another card's value, and every missing measurement renders "—".
 */
export function KpiStrip({ summary }: { summary: RunSummaryDetail }) {
  const c = summary.counts
  const delta = summary.delta_abs ?? null
  const nVal = summary.splits?.val ?? summary.tasks?.length ?? null

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6"
    >
      <Kpi
        label="baseline val"
        hint={seHint(summary.baseline_val, summary.baseline_stderr, nVal)}
        title="The unmodified seed's score on val — the number every candidate must beat."
      >
        <CountUp value={summary.baseline_val} format={pct} />
      </Kpi>

      <Kpi
        label="best val"
        tone="text-accent"
        hint={summary.best_id ? `candidate ${summary.best_id}` : undefined}
        title="Best val score any accepted candidate reached. Selection metric, not the result."
      >
        <CountUp value={summary.best_val} format={pct} />
      </Kpi>

      <Kpi
        label="Δ val vs baseline"
        tone={delta == null ? undefined : delta > 0 ? 'text-accepted' : delta < 0 ? 'text-rejected' : undefined}
        hint={
          summary.delta_pct != null
            ? `${summary.delta_pct > 0 ? '+' : ''}${summary.delta_pct}% relative`
            : 'relative % undefined off a zero baseline'
        }
        title="Absolute change in val. The relative % is undefined when the baseline is 0."
      >
        <CountUp
          value={delta}
          format={(v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(3)}`)}
        />
      </Kpi>

      <Kpi
        label={summary.test_sealed ? 'sealed test' : 'test (unsealed)'}
        tone="text-primary"
        hint={passKHint(summary.test_pass_k) ?? seHint(summary.test_reward, summary.test_stderr)}
        title="Scored exactly once on data the optimizer never saw. This is the honest headline."
      >
        <CountUp value={summary.test_reward} format={pct} />
      </Kpi>

      <Kpi
        label="verdicts"
        hint={`${c?.accepted ?? 0} accept · ${c?.rejected ?? 0} reject · ${c?.indecisive ?? 0} indecisive · ${c?.failed ?? 0} no-measure`}
        title="Candidate outcomes. Indecisive means the gate refused to judge — missing data, not a bad edit."
      >
        <span className="tnum">
          {c ? c.total - (c.seed ?? 0) : 0}
          <span className="ml-1 text-xs font-normal text-muted">candidates</span>
        </span>
      </Kpi>

      <Kpi
        label="spend"
        hint={
          summary.cost
            ? `opt ${usd(summary.cost.optimizer_usd)} · eval ${usd(summary.cost.runner_usd)} · intake ${usd(summary.cost.intake_usd ?? 0)}`
            : undefined
        }
        title="Total recorded cost across intake, optimizer calls and evaluations."
      >
        <CountUp value={summary.cost?.total_usd ?? null} format={usd} />
      </Kpi>

      <Kpi label="tokens" hint={tokenHint(summary)}>
        <CountUp value={summary.tokens ?? null} format={compactNum} />
      </Kpi>

      <Kpi
        label="measured time"
        hint={`opt ${duration(summary.optimizer_seconds)} · eval ${duration(summary.runner_seconds)}`}
        title="Sum of measured optimizer + evaluation + intake time (excludes idle gaps)."
      >
        {duration(summary.wall_clock_seconds)}
      </Kpi>

      <Kpi label="frontier" hint="gated leaves with no accepted child">
        {summary.frontier ?? '—'}
      </Kpi>

      <Kpi label="events" hint="every line in events.jsonl">
        {summary.event_count ?? '—'}
      </Kpi>

      <Kpi
        label="val tasks × trials"
        hint={summary.tasks?.length ? `${summary.tasks.length} task ids recorded` : undefined}
      >
        {nVal ?? '—'}
      </Kpi>

      <Kpi
        label="unattributed spend"
        tone={
          Math.abs(summary.cost_ledger?.unattributed_usd ?? 0) > 0.0005
            ? 'text-accent'
            : undefined
        }
        hint="recorded spend the event rows cannot explain"
      >
        {summary.cost_ledger ? usd(summary.cost_ledger.unattributed_usd) : '—'}
      </Kpi>
    </motion.div>
  )
}

function tokenHint(s: RunSummaryDetail): string | undefined {
  const t = s.tokens_by_role
  if (!t) return undefined
  return `runner ${compactNum(t.runner)} · opt ${compactNum(t.optimizer)} · intake ${compactNum(t.intake)}`
}

function Kpi({
  label,
  children,
  tone,
  hint,
  title,
}: {
  label: string
  children: ReactNode
  tone?: string
  hint?: string
  title?: string
}) {
  return (
    <motion.div variants={fadeUpItem}>
      <Card className="h-full px-3 py-2.5" title={title}>
        <div className="eyebrow">{label}</div>
        <div className={cn('tnum mt-1 text-lg font-semibold', tone ?? 'text-foreground')}>
          {children}
        </div>
        {hint && <div className="tnum mt-0.5 text-[10px] leading-snug text-muted">{hint}</div>}
      </Card>
    </motion.div>
  )
}
