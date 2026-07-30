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
  /** Stated, never assumed — the label says which way is better. */
  direction?: 'higher_is_better' | 'lower_is_better'
  width?: number
  height?: number
  className?: string
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

/** The text equivalent of the shape. Exported so a test asserts the same sentence
 * the screen reader hears. */
export function sparklineLabel(values: number[], direction = 'higher_is_better'): string {
  if (values.length === 0) return 'No score history yet.'
  const first = values[0]
  const last = values[values.length - 1]
  const better = direction === 'lower_is_better' ? last < first : last > first
  const worse = direction === 'lower_is_better' ? last > first : last < first
  const trend = better ? 'improved' : worse ? 'regressed' : 'unchanged'
  const arrow = direction === 'lower_is_better' ? 'lower is better' : 'higher is better'
  return `Best score over ${values.length} evaluated candidate${values.length === 1 ? '' : 's'}: ${trend} from ${pct(first)} to ${pct(last)} (${arrow}).`
}

export function Sparkline({
  values,
  direction = 'higher_is_better',
  width = 96,
  height = 26,
  className,
}: SparklineProps) {
  const label = sparklineLabel(values, direction)
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
  // y is inverted (SVG grows downward) and, for lower-is-better, inverted again so
  // "up and to the right" always means "better" whatever the metric direction is.
  const norm = (v: number) =>
    direction === 'lower_is_better' ? (max - v) / span : (v - min) / span
  const pts = values.map((v, i) => `${(i * dx).toFixed(2)},${(height - 2 - norm(v) * (height - 4)).toFixed(2)}`)

  const improved = direction === 'lower_is_better'
    ? values[values.length - 1] < values[0]
    : values[values.length - 1] > values[0]

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
        <span aria-hidden>{improved ? '↑' : '→'}</span>{' '}
        {direction === 'lower_is_better' ? 'lower' : 'higher'} is better
      </span>
    </span>
  )
}
