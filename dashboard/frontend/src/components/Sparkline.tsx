/** Inline-SVG sparkline of the running-best curve. No chart dependency (#138).
 *
 * A sparkline conveys information, so it is not decoration: the <svg> carries
 * role="img" and an aria-label that states the shape in words, and the same sentence
 * is rendered as visible text next to it. Nothing here animates — the shape is static,
 * so there is nothing for prefers-reduced-motion to suppress.
 */

export interface SparklineProps {
  /** Running-best values, oldest first. Fewer than 2 points renders nothing. */
  values: number[]
  width?: number
  height?: number
  className?: string
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

/** The text equivalent of the shape. Exported so a test asserts the same sentence
 * the screen reader hears.
 *
 * Reward in cap-evolve is higher-is-better, full stop: every gate in the repo accepts
 * on `val > parent_val` (`gate.decide`) and nothing emits a direction. There used to be
 * a `lower_is_better` branch here, wired to a hardcoded `metric_direction`; it was
 * unreachable flexibility whose only test asserted a value the backend cannot produce
 * (#234 review, nit 6). State the constant instead of branching on a fiction. */
export function sparklineLabel(values: number[]): string {
  if (values.length === 0) return 'No score history yet.'
  const first = values[0]
  const last = values[values.length - 1]
  const trend = last > first ? 'improved' : last < first ? 'regressed' : 'unchanged'
  return `Best score over ${values.length} evaluated candidate${values.length === 1 ? '' : 's'}: ${trend} from ${pct(first)} to ${pct(last)} (higher is better).`
}

export function Sparkline({ values, width = 96, height = 26, className }: SparklineProps) {
  const label = sparklineLabel(values)
  if (values.length < 2) {
    // One point is not a trend: say so in words rather than drawing a flat line that
    // would read as "no progress".
    return (
      <span className={className} data-testid="sparkline-empty">
        <span className="text-xs text-muted">{label}</span>
      </span>
    )
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const dx = width / (values.length - 1)
  // y is inverted (SVG grows downward), so "up and to the right" means better.
  const norm = (v: number) => (v - min) / span
  const pts = values.map((v, i) => `${(i * dx).toFixed(2)},${(height - 2 - norm(v) * (height - 4)).toFixed(2)}`)

  const improved = values[values.length - 1] > values[0]

  return (
    <span className={className}>
      <svg
        role="img"
        aria-label={label}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible align-middle"
        data-testid="sparkline"
      >
        <polyline
          points={pts.join(' ')}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <circle
          cx={(values.length - 1) * dx}
          cy={height - 2 - norm(values[values.length - 1]) * (height - 4)}
          r={2.5}
          fill="currentColor"
        />
      </svg>
      {/* Direction is never colour-only: the arrow glyph and the words carry it too. */}
      <span className="tnum ml-1.5 align-middle text-xs text-muted">
        <span aria-hidden>{improved ? '↑' : '→'}</span> higher is better
      </span>
    </span>
  )
}
