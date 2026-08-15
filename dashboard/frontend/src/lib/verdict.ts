/** One vocabulary for run status and candidate verdicts, shared by every panel.
 *
 * Colour is never the only carrier: each entry has an icon name and a label, and the
 * four verdict hues stay separable for the common colour-vision deficiencies.
 */
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleDot,
  CircleSlash,
  HelpCircle,
  Hourglass,
  PauseCircle,
  Wallet,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { NodeStatus, RunStatus, Verdict } from './types'

export interface Meta {
  label: string
  /** Tailwind text colour class. */
  tone: string
  /** Tailwind border colour class, for chips/rows. */
  ring: string
  Icon: LucideIcon
  /** One line explaining what the state MEANS — used in tooltips and empty states. */
  blurb: string
}

export const RUN_STATUS: Record<RunStatus, Meta> = {
  running: {
    label: 'running',
    tone: 'text-primary',
    ring: 'border-primary/50',
    Icon: CircleDot,
    blurb: 'The event log is still moving.',
  },
  awaiting_agent: {
    label: 'awaiting agent',
    tone: 'text-indecisive',
    ring: 'border-indecisive/50',
    Icon: Hourglass,
    blurb:
      'Baseline is done and `cap-evolve run` handed the loop to the coding agent. ' +
      'Nothing is wrong — no candidate has been committed yet.',
  },
  completed: {
    label: 'completed',
    tone: 'text-accepted',
    ring: 'border-accepted/50',
    Icon: CheckCircle2,
    blurb: 'Finalize scored the sealed test split — the run reached its end.',
  },
  budget_exhausted: {
    label: 'budget exhausted',
    tone: 'text-accent',
    ring: 'border-accent/50',
    Icon: Wallet,
    blurb: 'A budget cap was reached and the test split was never sealed.',
  },
  stalled: {
    label: 'stalled',
    tone: 'text-accent',
    ring: 'border-accent/50',
    Icon: PauseCircle,
    blurb: 'The algorithm declared it had stopped improving, without finalizing.',
  },
  interrupted: {
    label: 'interrupted',
    tone: 'text-failed',
    ring: 'border-failed/50',
    Icon: AlertTriangle,
    blurb: 'No finalize and no recent event — the run died or was killed.',
  },
  failed: {
    label: 'failed',
    tone: 'text-rejected',
    ring: 'border-rejected/50',
    Icon: XCircle,
    blurb: 'Nothing was ever evaluated.',
  },
  unknown: {
    label: 'status not recorded',
    tone: 'text-muted',
    ring: 'border-line',
    Icon: HelpCircle,
    blurb:
      'This run dir carries no status evidence — typically an artifact exported before ' +
      'status was derived. It is NOT a failure; nothing is known either way.',
  },
}

export const VERDICT: Record<Verdict, Meta> = {
  accept: {
    label: 'accept',
    tone: 'text-accepted',
    ring: 'border-accepted/50',
    Icon: CheckCircle2,
    blurb: 'The paired improvement cleared the significance bar.',
  },
  reject: {
    label: 'reject',
    tone: 'text-rejected',
    ring: 'border-rejected/50',
    Icon: XCircle,
    blurb: 'Measured, but the improvement did not clear the bar.',
  },
  indecisive: {
    label: 'indecisive',
    tone: 'text-indecisive',
    ring: 'border-indecisive/50',
    Icon: HelpCircle,
    blurb:
      'The gate REFUSED to judge — too little of the split ran, or the candidate ' +
      'edited a protected file. This is missing data, not a bad edit.',
  },
  'no measurement': {
    label: 'no measurement',
    tone: 'text-failed',
    ring: 'border-failed/50',
    Icon: CircleSlash,
    blurb: 'The candidate produced no score at all.',
  },
}

export const NODE_STATUS: Record<NodeStatus, Meta> = {
  seed: {
    label: 'seed',
    tone: 'text-seed',
    ring: 'border-seed/50',
    Icon: CircleDashed,
    blurb: 'The unmodified starting capability — the number everything must beat.',
  },
  accepted: VERDICT.accept,
  rejected: VERDICT.reject,
  indecisive: VERDICT.indecisive,
  failed: { ...VERDICT['no measurement'], label: 'failed' },
}

/** CSS custom-property name for a node status, for SVG/chart fills. */
export function statusVar(status: NodeStatus): string {
  return `var(--${status === 'accepted' ? 'accepted' : status === 'rejected' ? 'rejected' : status})`
}
