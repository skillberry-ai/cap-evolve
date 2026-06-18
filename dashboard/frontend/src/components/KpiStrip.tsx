import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import type { RunSummaryDetail } from '../lib/types'
import { compactNum, duration, pct, signedPct, usd, deltaTone } from '../lib/format'
import { fadeUpItem, staggerContainer } from '../lib/motion'
import { CountUp } from './CountUp'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

const TONE = { up: 'text-accepted', down: 'text-rejected', flat: 'text-muted' } as const

/** Sticky, data-dense KPI header. Numbers count up on change. */
export function KpiStrip({ summary }: { summary: RunSummaryDetail }) {
  const c = summary.counts
  const tone = deltaTone(summary.delta_pct)
  const dollarPerPct =
    summary.cost?.total_usd != null && summary.delta_pct && summary.delta_pct > 0
      ? summary.cost.total_usd / summary.delta_pct
      : null

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6"
    >
      <Kpi label="best" tone="accent">
        <CountUp value={summary.best_val} format={pct} />
      </Kpi>
      <Kpi label="baseline">
        <CountUp value={summary.baseline_val} format={pct} />
      </Kpi>
      <Kpi label="Δ vs baseline" className={TONE[tone]}>
        <CountUp value={summary.delta_pct} format={(v) => signedPct(v)} />
      </Kpi>
      <Kpi label="sealed test" tone="accent" hint={summary.test_pass_k != null ? `pass^k ${pct(summary.test_pass_k)}` : undefined}>
        <CountUp value={summary.test_reward} format={pct} />
      </Kpi>
      <Kpi label="cost (opt+run)" hint={summary.cost ? `${usd(summary.cost.optimizer_usd)} + ${usd(summary.cost.runner_usd)}` : undefined}>
        <CountUp value={summary.cost?.total_usd ?? null} format={usd} />
      </Kpi>
      <Kpi label="tokens">
        <CountUp value={summary.tokens ?? null} format={compactNum} />
      </Kpi>

      <Kpi label="accepted" tone="accepted">{c?.accepted ?? 0}</Kpi>
      <Kpi label="rejected" tone="rejected">{c?.rejected ?? 0}</Kpi>
      <Kpi label="failed">{c?.failed ?? 0}</Kpi>
      <Kpi label="frontier">{summary.frontier ?? 0}</Kpi>
      <Kpi label="wall clock">{duration(summary.wall_clock_seconds)}</Kpi>
      <Kpi label="$ / +1%">{dollarPerPct != null ? usd(dollarPerPct) : '—'}</Kpi>
    </motion.div>
  )
}

function Kpi({
  label,
  children,
  tone,
  hint,
  className,
}: {
  label: string
  children: ReactNode
  tone?: 'accent' | 'accepted' | 'rejected'
  hint?: string
  className?: string
}) {
  const toneClass =
    tone === 'accent'
      ? 'text-accent'
      : tone === 'accepted'
        ? 'text-accepted'
        : tone === 'rejected'
          ? 'text-rejected'
          : 'text-foreground'
  return (
    <motion.div variants={fadeUpItem}>
      <Card className="px-3 py-2.5">
        <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
        <div className={cn('tnum mt-0.5 text-lg font-semibold', toneClass, className)}>{children}</div>
        {hint && <div className="tnum text-[10px] text-muted">{hint}</div>}
      </Card>
    </motion.div>
  )
}
