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

/**
 * `4 accept · 5 reject · 0 no-measure` — one clause per verdict the payload actually
 * counted. A category the payload never enumerated is DROPPED, not printed: the static
 * `run_full` export carries `{accepted, rejected, failed, seed, total}` with no
 * `indecisive` key, and interpolating it straight rendered `undefined indecisive` on
 * screen — the same class of defect as `pass^k NaN%`, a missing measurement wearing a
 * value's clothes. `counts.indecisive` is optional in the type for exactly this reason.
 */
export function verdictBreakdown(c: NonNullable<RunSummaryDetail['counts']>): string | undefined {
  const parts = ([
    [c.accepted, 'accept'],
    [c.rejected, 'reject'],
    [c.indecisive, 'indecisive'],
    [c.failed, 'no-measure'],
  ] as const)
    .filter(([n]) => isMeasured(n))
    .map(([n, word]) => `${n} ${word}`)
  return parts.length ? parts.join(' · ') : undefined
}

/** ±SE suffix, or nothing when the run recorded no uncertainty. A mean with no SE and
 *  no n is exactly the sloppiness this project exists to avoid — so when SE is missing
 *  we say so rather than implying the number is exact. */
function seHint(value: number | null | undefined, se: number | null | undefined, n?: number | null) {
  if (value == null) return undefined
  if (se == null) return 'no stderr recorded'
  return `± ${se.toFixed(3)}${n ? ` · n=${n}` : ''}`
}

const signed = (v: number | null | undefined, digits = 3) =>
  !isMeasured(v) ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}`

/**
 * The four numbers a run is judged on, then one dense strip of accounting.
 *
 * This used to be twelve identical cards, six of which read `0` / `—` on most runs:
 * `frontier`, `events` and `unattributed spend` are audit details that belong to the
 * Candidates and Cost tabs, and giving them the same visual weight as the sealed test
 * flattened the hierarchy into a wall of equal boxes. Hierarchy now comes from size and
 * grouping (not colour): four large outcome tiles, then a single accounting row where an
 * unrecorded measurement says "not recorded" instead of showing a confident zero.
 */
export function KpiStrip({ summary }: { summary: RunSummaryDetail }) {
  const c = summary.counts
  const delta = summary.delta_abs ?? null
  const nVal = summary.splits?.val ?? summary.tasks?.length ?? null
  const cands = c ? c.total - (c.seed ?? 0) : 0
  const tokens = summary.tokens
  // $0 recorded after real calls means the runner reported no cost. That covers BOTH a
  // zero-API adapter (genuinely free) and a proxy that returns no usage (real spend,
  // unpriced) — the run dir cannot tell them apart, so the wording asserts only what is
  // certain: no per-call cost was reported. Same treatment as the tokens fact beside it.
  const unmetered = summary.cost?.metered === false
  const t = summary.tokens_by_role

  // "no stderr recorded" must only be said when NOTHING recorded it. The baseline's SE
  // also lives on its evaluation row, and an export predating the top-level
  // `baseline_stderr` field made this tile claim no uncertainty was measured while the
  // Cost tab printed "53.6% ± 5.6%" two rows below it.
  const baselineSe =
    summary.baseline_stderr ??
    summary.evaluations?.find((e) => e.kind === 'baseline')?.stderr ??
    null

  // The sealed test only means something against the SEED's score on the same split.
  const testDelta = summary.test_delta ?? null
  const testHint = isMeasured(summary.test_baseline_reward)
    ? `seed ${pct(summary.test_baseline_reward)} · Δ ${signed(testDelta)}`
    : (passKHint(summary.test_pass_k) ?? seHint(summary.test_reward, summary.test_stderr))

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="space-y-2">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Kpi
          label="baseline val"
          hint={seHint(summary.baseline_val, baselineSe, nVal)}
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
          tone={
            delta == null ? undefined : delta > 0 ? 'text-accepted' : delta < 0 ? 'text-rejected' : undefined
          }
          hint={
            summary.delta_pct != null
              ? `${summary.delta_pct > 0 ? '+' : ''}${summary.delta_pct}% relative`
              : // A null delta_pct has TWO causes and they are not the same statement.
                // Only one of them is "the baseline was 0"; the other is "there is no
                // baseline (or no best val) to divide yet", which is what every live
                // snapshot taken before the seed finishes scoring looks like. Printing
                // the zero-baseline sentence there invents a measurement.
                summary.baseline_val == null || summary.best_val == null
                ? 'no baseline measured yet — nothing to compare'
                : 'relative % undefined off a zero baseline'
          }
          title="Absolute change in val. The relative % is undefined when the baseline is 0, and there is no % at all until both the baseline and a best val exist."
        >
          <CountUp value={delta} format={(v) => signed(v)} />
        </Kpi>

        <Kpi
          label={summary.test_sealed ? 'sealed test' : 'test — not sealed yet'}
          tone={summary.test_reward == null ? 'text-muted' : 'text-primary'}
          hint={
            summary.test_reward == null
              ? 'scored once by `cap-evolve finalize`, on data the optimizer never saw'
              : testHint
          }
          title="Scored exactly once on data the optimizer never saw. This is the honest headline."
        >
          <CountUp value={summary.test_reward} format={pct} />
        </Kpi>
      </div>

      {/* Accounting: one row, six facts, no card per number. */}
      <motion.div variants={fadeUpItem}>
        <Card className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-3 lg:grid-cols-6">
          <Fact label="verdicts" value={`${cands} candidate${cands === 1 ? '' : 's'}`}>
            {c ? (verdictBreakdown(c) ?? 'no verdict recorded') : 'no candidate recorded'}
          </Fact>
          <Fact
            label="spend"
            value={unmetered ? 'not reported' : usd(summary.cost?.total_usd)}
            dim={unmetered}
          >
            {unmetered
              ? 'this runner reports no per-call cost — $0 here would be a guess, not a measurement'
              : summary.cost
                ? `opt ${usd(summary.cost.optimizer_usd)} · eval ${usd(summary.cost.runner_usd)} · intake ${usd(summary.cost.intake_usd ?? 0)}`
                : 'no spend accounting'}
          </Fact>
          <Fact label="measured time" value={duration(summary.wall_clock_seconds)}>
            opt {duration(summary.optimizer_seconds)} · eval {duration(summary.runner_seconds)}
          </Fact>
          <Fact
            label="tokens"
            value={tokens ? compactNum(tokens) : 'not recorded'}
            dim={!tokens}
          >
            {tokens && t
              ? `runner ${compactNum(t.runner)} · opt ${compactNum(t.optimizer)}`
              : 'this runner does not report token counts'}
          </Fact>
          <Fact label="val tasks" value={nVal == null ? '—' : String(nVal)}>
            {summary.splits
              ? `train ${summary.splits.train ?? '—'} · test ${summary.splits.test ?? '—'}`
              : 'splits not recorded'}
          </Fact>
          {/* An absent event_count is NOT zero events: the run dir may simply not ship
              its stream any more. "0 lines in events.jsonl" asserted a file we never
              read. */}
          <Fact
            label="events"
            value={isMeasured(summary.event_count) ? String(summary.event_count) : 'not recorded'}
            dim={!isMeasured(summary.event_count)}
          >
            {isMeasured(summary.event_count)
              ? 'lines in events.jsonl'
              : 'this run dir ships no events.jsonl'}
          </Fact>
        </Card>
      </motion.div>
    </motion.div>
  )
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
      <Card className="h-full px-4 py-3" title={title}>
        <div className="eyebrow">{label}</div>
        <div className={cn('tnum mt-1.5 text-2xl font-semibold', tone ?? 'text-foreground')}>
          {children}
        </div>
        {hint && <div className="tnum mt-1 text-[11px] leading-snug text-muted">{hint}</div>}
      </Card>
    </motion.div>
  )
}

function Fact({
  label,
  value,
  children,
  dim,
}: {
  label: string
  value: string
  children: ReactNode
  dim?: boolean
}) {
  return (
    <div className="min-w-0">
      <div className="eyebrow">{label}</div>
      <div className={cn('tnum text-sm font-semibold', dim ? 'text-muted' : 'text-foreground')}>
        {value}
      </div>
      <div className="tnum text-[11px] leading-snug text-muted">{children}</div>
    </div>
  )
}
