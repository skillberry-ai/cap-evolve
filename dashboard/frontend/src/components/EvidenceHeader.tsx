/** The evidence header (#138): phase pipeline · now · sparkline · burn · evidence line.
 *
 * Every number here is attributed — each cell's `title` names the file or event the
 * value came from, because this epic has already shipped a cost meter that overstated
 * spend 2x and cost bars that didn't sum to their own total. Nothing is re-derived
 * client-side: the burn comes from `summary.pipeline.burn` (state.json's `Spent`, or
 * `eventstream.accrue_totals` over the log before a Spent exists), the scores from
 * `baseline.json` / the gated val evals / `final.json`.
 *
 * Complementary to the StatusBadge (#118), not a second opinion: the badge answers "is
 * this process alive", this header answers "what stage, what now, is it improving, what
 * has it cost". The header never claims a run is live or done.
 */
import { useEffect, useState } from 'react'
import type { RunDetail } from '../lib/types'
import { cumulativeBest } from '../lib/bestCurve'
import { compactNum, duration, pct, signedPct, usd } from '../lib/format'
import { Card } from './ui/Card'
import { Sparkline } from './Sparkline'
import { cn } from '../lib/cn'

/** Seconds since an epoch timestamp, ticking once a second. `null` t → null. */
function useSecondsSince(t: number | null | undefined): number | null {
  const [now, setNow] = useState(() => Date.now() / 1000)
  useEffect(() => {
    if (t == null) return
    // 1s text tick, not an animation: prefers-reduced-motion is about motion, and a
    // clock that stops updating would be a wrong number rather than a calmer one.
    const id = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(id)
  }, [t])
  if (t == null) return null
  return Math.max(0, now - t)
}

export function EvidenceHeader({ detail }: { detail: RunDetail }) {
  const s = detail.summary
  const p = s.pipeline
  const inState = useSecondsSince(p?.now?.since ?? null)
  const sinceEvent = useSecondsSince(p?.now?.t ?? null)

  // The running-best series — the same `cumulativeBest` the overview chart draws, so
  // the sparkline and the chart can never disagree about the curve.
  const best = cumulativeBest(detail.graph.nodes).map((c) => c.best)
  const burn = p?.burn
  const direction = s.metric_direction ?? 'higher_is_better'

  return (
    <Card className="p-4" data-testid="evidence-header">
      {p?.phases?.length ? <PhasePipeline phases={p.phases} algorithm={s.algorithm} /> : null}

      {p?.now?.line ? (
        <p className="mt-3 flex flex-wrap items-baseline gap-x-2 text-sm" data-testid="now-line">
          <span className="text-[10px] uppercase tracking-wide text-muted">now</span>
          <span className="font-mono text-xs text-foreground">{p.now.line}</span>
          {sinceEvent != null && (
            <span className="tnum text-xs text-muted" title="Wall clock since this event's own timestamp">
              {duration(sinceEvent)} ago
            </span>
          )}
          {inState != null && p.current && (
            <span
              className="tnum text-xs text-muted"
              title={`Wall clock since the first event of the ${p.current} phase`}
            >
              · {duration(inState)} in {p.current}
            </span>
          )}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-start gap-x-8 gap-y-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted">best on val</div>
          <div className="mt-1 flex items-center text-accent" data-testid="sparkline-cell">
            <Sparkline values={best} direction={direction} />
          </div>
        </div>

        <Cell
          label="burn"
          value={usd(burn?.usd ?? null)}
          // No rate for a finished run or under a minute of elapsed time: a burn rate
          // answers "what is this costing right now", and there is no honest answer
          // once the run is over (see dashboard._rate).
          hint={burn?.usd_per_min != null ? `${usd(burn.usd_per_min)}/min` : undefined}
          title={
            burn?.source === 'spent'
              ? 'state.json Spent.total_usd (runner + optimizer + intake) — the same total the budget check and the KPI strip use.'
              : 'Accumulated from events.jsonl by eventstream.accrue_totals: runner cost from `evaluate`, optimizer cost from `step`-likes, intake from `intake` — each counted once.'
          }
        />
        <Cell
          label="tokens"
          value={compactNum(burn?.tokens ?? null)}
          hint={burn?.tokens_per_min != null ? `${compactNum(burn.tokens_per_min)}/min` : undefined}
          title={
            burn?.source === 'spent'
              ? 'state.json Spent: runner_tokens + optimizer_tokens + intake_tokens.'
              : 'Accumulated from events.jsonl by eventstream.accrue_totals.'
          }
        />
      </div>

      {/* ---- the evidence line: the honest-eval story, always visible ---- */}
      <dl
        className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-border pt-3"
        data-testid="evidence-line"
      >
        <Fact label="baseline (seed on val)" value={pct(s.baseline_val)} title="baseline.json → val.reward" />
        <Fact label="best on val" value={pct(s.best_val)} title="the highest gated val score in events.jsonl" />
        {/* A % change off a zero baseline is undefined — reduce_run leaves delta_pct
            null there and only delta_abs is honest, so label it as POINTS, not %. */}
        {s.delta_pct != null ? (
          <Fact
            label="Δ vs baseline"
            value={signedPct(s.delta_pct)}
            title="computed: (best val − baseline val) / |baseline val|"
          />
        ) : (
          <Fact
            label="Δ vs baseline"
            value={s.delta_abs != null ? `${s.delta_abs > 0 ? '+' : ''}${(s.delta_abs * 100).toFixed(1)} pts` : '—'}
            title="computed: best val − baseline val, in points. A % change off a zero baseline is undefined, so the absolute delta is shown instead."
          />
        )}
        <Fact
          label="sealed test"
          value={s.test_reward != null ? pct(s.test_reward) : s.test_sealed ? 'sealed' : 'not finalized'}
          title="final.json → test.reward — scored once, on data the optimizer never saw"
        />
        <Fact
          label="metric"
          value={direction === 'lower_is_better' ? 'lower is better' : 'higher is better'}
          title="Every gate in cap-evolve accepts on val > parent_val, so reward is higher-is-better."
        />
      </dl>
    </Card>
  )
}

function Cell({
  label,
  value,
  hint,
  title,
}: {
  label: string
  value: string
  hint?: string
  title?: string
}) {
  return (
    <div title={title}>
      <div className="text-[10px] uppercase tracking-wide text-muted">{label}</div>
      <div className="tnum mt-0.5 text-lg font-semibold text-foreground">{value}</div>
      {hint && <div className="tnum text-[10px] text-muted">{hint}</div>}
    </div>
  )
}

function Fact({ label, value, title }: { label: string; value: string; title: string }) {
  return (
    <div title={title}>
      <dt className="text-[10px] uppercase tracking-wide text-muted">{label}</dt>
      <dd className="tnum text-sm font-medium text-foreground">{value}</dd>
    </div>
  )
}

/** The stages, with the active one lit. State is icon + label + text, never colour
 * alone (the StatusBadge pairing); `aria-current="step"` marks the active stage. */
function PhasePipeline({
  phases,
  algorithm,
}: {
  phases: NonNullable<RunDetail['summary']['pipeline']>['phases']
  algorithm?: string | null
}) {
  return (
    <ol className="flex flex-wrap items-center gap-1.5" data-testid="phase-pipeline">
      {phases.map((ph, i) => {
        const label = ph.key === 'optimize' && algorithm ? `${ph.label} · ${algorithm}` : ph.label
        const glyph =
          ph.status === 'done' ? '✓' : ph.status === 'active' ? '●' : ph.status === 'skipped' ? '–' : '○'
        return (
          <li key={ph.key} className="flex items-center gap-1.5">
            <span
              aria-current={ph.status === 'active' ? 'step' : undefined}
              title={ph.detail}
              className={cn(
                'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs',
                ph.status === 'done'
                  ? 'border-accepted/40 text-accepted'
                  : ph.status === 'active'
                    ? 'border-accent/60 bg-accent/10 font-semibold text-accent'
                    : 'border-border text-muted',
              )}
            >
              <span aria-hidden>{glyph}</span>
              {label}
              <span className="sr-only"> ({ph.status})</span>
            </span>
            {i < phases.length - 1 && (
              <span className="text-muted" aria-hidden>
                →
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}
