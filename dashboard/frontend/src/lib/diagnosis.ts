import type { Diagnosis, Edit, SkippedEdit } from './types'

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
