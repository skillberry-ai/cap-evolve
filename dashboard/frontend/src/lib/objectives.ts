/** The run's declared multi-objective config (#676), read generically off its config
 * spec — `objectives`/`gate_mode` aren't keys with their own typed field on
 * RunSummaryDetail yet, they ride through as spec_groups items (see dashboard.py's
 * `_CONFIG_KEY_GROUPS`), so read them from whichever group they landed in rather than
 * assuming one. */
import type { RunSummaryDetail } from './types'

export interface ObjectiveSpec {
  name: string
  direction: string
}

function specItem(summary: RunSummaryDetail | undefined, key: string): unknown {
  const groups = summary?.config?.spec_groups ?? []
  for (const g of groups) {
    for (const item of g.items) {
      if (item.key === key) return item.value
    }
  }
  return undefined
}

/** The declared `objectives` list, normalized to `{name, direction}`. Entries that
 * aren't a `{name, ...}` object (an older/mangled spec read) are dropped rather than
 * faked — same rule as everywhere else absent data is shown as absent, not zero. */
export function getObjectives(summary: RunSummaryDetail | undefined): ObjectiveSpec[] {
  const value = specItem(summary, 'objectives')
  if (!Array.isArray(value)) return []
  return value
    .filter((o): o is { name: string; direction?: string } =>
      !!o && typeof o === 'object' && typeof (o as Record<string, unknown>).name === 'string')
    .map((o) => ({ name: o.name, direction: o.direction ?? 'maximize' }))
}

/** The declared `gate_mode`, or null when not set. */
export function getGateMode(summary: RunSummaryDetail | undefined): string | null {
  const value = specItem(summary, 'gate_mode')
  return typeof value === 'string' ? value : null
}
