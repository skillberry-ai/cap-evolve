/** Locale-aware display formatters for scores, deltas, cost, counts, time. */

const DASH = '—'

/** A 0..1 reward as a percentage, e.g. 0.752 -> "75.2%". */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return DASH
  return `${(v * 100).toFixed(digits)}%`
}

/** A delta percentage with explicit sign, e.g. 12.3 -> "+12.3%", -4 -> "-4.0%". */
export function signedPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return DASH
  const s = v > 0 ? '+' : ''
  return `${s}${v.toFixed(digits)}%`
}

/** US dollars, e.g. 0.0123 -> "$0.012", 12.5 -> "$12.50". */
export function usd(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return DASH
  const digits = Math.abs(v) < 1 ? 3 : 2
  return `$${v.toFixed(digits)}`
}

/** Compact integers, e.g. 1500 -> "1.5K", 2_300_000 -> "2.3M". */
export function compactNum(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return DASH
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(v)
}

/** Seconds as a short human duration, e.g. 75 -> "1m 15s", 3661 -> "1h 1m". */
export function duration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return DASH
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

/** Sign class for delta coloring (accepted/rejected/muted). */
export function deltaTone(v: number | null | undefined): 'up' | 'down' | 'flat' {
  if (v == null || Number.isNaN(v) || v === 0) return 'flat'
  return v > 0 ? 'up' : 'down'
}
