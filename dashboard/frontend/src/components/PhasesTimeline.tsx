import { motion } from 'framer-motion'
import { Check, Loader2 } from 'lucide-react'
import type { RunDetail } from '../lib/types'
import { derivePhases, type PhaseStep } from '../lib/phases'
import { fadeUpItem, staggerContainer } from '../lib/motion'
import { Card } from './ui/Card'
import { cn } from '../lib/cn'

export function PhasesTimeline({ detail }: { detail: RunDetail }) {
  const phases = derivePhases(detail)
  return (
    <motion.ol
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="grid gap-3 md:grid-cols-2 lg:grid-cols-3"
    >
      {phases.map((p, i) => (
        <motion.li key={p.key} variants={fadeUpItem}>
          <PhaseCard step={p} index={i + 1} />
        </motion.li>
      ))}
    </motion.ol>
  )
}

function PhaseCard({ step, index }: { step: PhaseStep; index: number }) {
  const tone =
    step.status === 'done'
      ? 'border-accepted/40'
      : step.status === 'active'
        ? 'border-primary/60'
        : 'border-border'
  return (
    <Card className={cn('relative h-full p-4', tone)}>
      {step.status === 'active' && (
        <span className="absolute right-3 top-3 h-2 w-2 rounded-full bg-primary animate-pulse-ring" aria-hidden />
      )}
      <div className="flex items-center gap-2">
        <Marker status={step.status} index={index} />
        <span className="font-medium">{step.label}</span>
      </div>
      <p className="mt-2 text-xs text-muted">{step.detail}</p>
      {step.metrics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {step.metrics.map((m) => (
            <div key={m.label}>
              <span className="tnum text-sm text-foreground">{m.value}</span>
              <span className="ml-1 text-[10px] uppercase tracking-wide text-muted">{m.label}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function Marker({ status, index }: { status: PhaseStep['status']; index: number }) {
  const base = 'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold'
  if (status === 'done')
    return (
      <span className={cn(base, 'bg-accepted/20 text-accepted')} aria-label="done">
        <Check size={14} />
      </span>
    )
  if (status === 'active')
    return (
      <span className={cn(base, 'bg-primary/20 text-primary')} aria-label="active">
        <Loader2 size={14} className="animate-spin" />
      </span>
    )
  return <span className={cn(base, 'bg-surface-2 text-muted')}>{index}</span>
}
