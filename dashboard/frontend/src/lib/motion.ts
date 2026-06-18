/** Shared Framer Motion tokens + a reduced-motion guard (spec §4a). */
import type { Variants, Transition } from 'framer-motion'

export const DUR = { micro: 0.12, standard: 0.2, enter: 0.28, complex: 0.4 } as const

export const springGrow: Transition = { type: 'spring', stiffness: 260, damping: 24 }
export const easeEnter: Transition = { duration: DUR.enter, ease: [0.22, 1, 0.36, 1] }
export const easeExit: Transition = { duration: DUR.enter * 0.65, ease: [0.4, 0, 1, 1] }

/** True when the OS asks for reduced motion. Components fall back to instant. */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** Staggered list/grid entrance (30–50ms per item). */
export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
}

export const fadeUpItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: easeEnter },
}
