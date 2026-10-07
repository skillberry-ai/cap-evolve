import type { Diagnosis, Edit, Outcomes, SkippedEdit } from './types'

/** The edits a diagnosis shipped: the top-level `edits[]` when present, else one edit per
 *  cluster carrying the compact schema's inline `edit` string (#625). */
export function diagnosisEdits(d: Diagnosis): Edit[] {
  if (Array.isArray(d.edits)) return d.edits
  return d.clusters
    .filter(c => c.edit)
    .map(c => ({ id: c.id, title: c.edit!, clusters: [c.id], verified: c.evidence }))
}

/** Skipped edits, whether written as `[{title, reason}]` or as a `{title: reason}` map. */
export function diagnosisSkipped(d: Diagnosis): SkippedEdit[] {
  const s = d.skipped
  if (!s) return []
  if (Array.isArray(s)) return s
  return Object.entries(s).map(([title, reason]) => ({ title, reason: String(reason) }))
}

export interface TaskGroup {
  key: string
  /** Group header, e.g. "failing, not in any cluster" — absent for a cluster's own group
   *  (its box in the clusters column IS the label). */
  label?: string
  tasks: string[]
}

/** Groups the task column the way the reference mockup's `flowSVG` does: each task sits
 *  under the first root-cause cluster that names it, plus two catch-all groups for a
 *  failing task no cluster named ("undiagnosed") and a regression no cluster named
 *  ("unpredicted"). A task is never listed twice. */
export function diagnosisTaskGroups(d: Diagnosis, outcomes?: Outcomes | null): TaskGroup[] {
  const seen = new Set<string>()
  const groups: TaskGroup[] = d.clusters.map(c => {
    const tasks = c.tasks.filter(t => !seen.has(t))
    tasks.forEach(t => seen.add(t))
    return { key: c.id, tasks }
  })

  const byStatus = (status: string) =>
    Object.keys(outcomes ?? {}).filter(t => outcomes![t] === status)
  // Without outcomes we still know which tasks the optimizer targeted — use the
  // clusters' own tasks as the best-effort "parent failing" set rather than showing none.
  const parentFailing = outcomes
    ? [...byStatus('fixed'), ...byStatus('still_failing')]
    : d.clusters.flatMap(c => c.tasks)
  const broke = outcomes ? byStatus('broke') : []

  const undiagnosed = parentFailing.filter(t => !seen.has(t))
  undiagnosed.forEach(t => seen.add(t))
  if (undiagnosed.length) groups.push({ key: '_undiagnosed', label: 'failing, not in any cluster', tasks: undiagnosed })

  const unpredicted = broke.filter(t => !seen.has(t))
  if (unpredicted.length) groups.push({ key: '_unpredicted', label: 'regressions (were passing)', tasks: unpredicted })

  return groups.filter(g => g.tasks.length > 0)
}
