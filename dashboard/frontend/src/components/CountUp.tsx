import { useEffect, useRef, useState } from 'react'
import { prefersReducedMotion } from '../lib/motion'

/** Tweens a number from its previous value to the new one (≈400ms, ease-out).
 * Renders via `format`. Instant when reduced-motion is requested. */
export function CountUp({
  value,
  format,
  durationMs = 400,
}: {
  value: number | null | undefined
  format: (v: number | null | undefined) => string
  durationMs?: number
}) {
  const [display, setDisplay] = useState<number | null>(value ?? null)
  const fromRef = useRef<number>(value ?? 0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (value == null || Number.isNaN(value)) {
      setDisplay(value ?? null)
      return
    }
    const from = fromRef.current
    const to = value
    if (prefersReducedMotion() || from === to) {
      fromRef.current = to
      setDisplay(to)
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      const v = from + (to - from) * eased
      setDisplay(v)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value, durationMs])

  return <span className="tnum">{format(display)}</span>
}
