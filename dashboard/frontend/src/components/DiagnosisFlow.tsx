import { useState, useMemo, useRef, useLayoutEffect, useCallback } from 'react'
import type { Diagnosis, NodeEdit, Outcomes } from '../lib/types'
import { editOutcome, diagnosisEdits, diagnosisSkipped, diagnosisTaskGroups } from '../lib/diagnosis'

interface DiagnosisFlowProps {
  diagnosis: Diagnosis
  outcomes?: Outcomes | null
  /** The node's recorded v2 edit (hypothesis + target_tasks): enables the outcome strip. */
  edit?: NodeEdit | null
}

/** One curved SVG link between two flow boxes (task→cluster or cluster→edit). */
interface FlowLink {
  a: string
  b: string
  d: string
  color: string
}

export function DiagnosisFlow({ diagnosis, outcomes, edit }: DiagnosisFlowProps) {
  const outcome = editOutcome(edit, outcomes)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const { clusters } = diagnosis
  const edits = useMemo(() => diagnosisEdits(diagnosis), [diagnosis])
  const skipped = diagnosisSkipped(diagnosis)
  const taskGroups = useMemo(() => diagnosisTaskGroups(diagnosis, outcomes), [diagnosis, outcomes])

  // Build connection map: task -> clusters, cluster -> edits
  const taskToClusters = useMemo(() => {
    const map = new Map<string, string[]>()
    clusters.forEach(c => {
      c.tasks.forEach(t => {
        if (!map.has(t)) map.set(t, [])
        map.get(t)!.push(c.id)
      })
    })
    return map
  }, [clusters])

  const clusterToEdits = useMemo(() => {
    const map = new Map<string, string[]>()
    edits.forEach(e => {
      e.clusters.forEach(c => {
        if (!map.has(c)) map.set(c, [])
        map.get(c)!.push(e.id)
      })
    })
    return map
  }, [edits])

  // Get task status from outcomes
  const getTaskStatus = (taskId: string) => outcomes?.[taskId] ?? 'unknown'
  const tasksWith = (status: string) =>
    Object.keys(outcomes ?? {}).filter(t => outcomes![t] === status)

  const getTaskColor = (status: string) => {
    switch (status) {
      case 'fixed':
        return 'var(--accepted)'
      case 'broke':
        return 'var(--rejected)'
      case 'still_failing':
        return 'var(--failed)'
      case 'still_passing':
        return 'var(--muted)'
      default:
        return 'var(--border)'
    }
  }

  // Check if a node should be highlighted
  const isHighlighted = (nodeId: string, nodeType: 'task' | 'cluster' | 'edit') => {
    if (!hoveredNode) return false

    const [type, id] = hoveredNode.split(':')

    if (type === 'task') {
      if (nodeType === 'task') return id === nodeId
      if (nodeType === 'cluster') return taskToClusters.get(id)?.includes(nodeId)
      if (nodeType === 'edit') {
        const clusterIds = taskToClusters.get(id) || []
        return clusterIds.some(cid => clusterToEdits.get(cid)?.includes(nodeId))
      }
    }

    if (type === 'cluster') {
      if (nodeType === 'cluster') return id === nodeId
      if (nodeType === 'task') return taskToClusters.get(nodeId)?.includes(id)
      if (nodeType === 'edit') return clusterToEdits.get(id)?.includes(nodeId)
    }

    if (type === 'edit') {
      if (nodeType === 'edit') return id === nodeId
      if (nodeType === 'cluster') return clusterToEdits.get(nodeId)?.includes(id)
      if (nodeType === 'task') {
        const edit = edits.find(e => e.id === id)
        if (!edit) return false
        return edit.clusters.some(cid => taskToClusters.get(nodeId)?.includes(cid))
      }
    }

    return false
  }

  // Curved connector lines between the three columns (the actual "flow" in the flow
  // diagram): measured off the rendered DOM rather than computed analytically like the
  // reference mockup's flowSVG, since React already lays the cards out for us.
  const flowRef = useRef<HTMLDivElement | null>(null)
  const nodeRefs = useRef(new Map<string, HTMLDivElement>())
  const setNodeRef = useCallback(
    (key: string) => (el: HTMLDivElement | null) => {
      if (el) nodeRefs.current.set(key, el)
      else nodeRefs.current.delete(key)
    },
    [],
  )
  const [links, setLinks] = useState<FlowLink[]>([])
  const [flowSize, setFlowSize] = useState({ w: 0, h: 0 })

  useLayoutEffect(() => {
    const recompute = () => {
      const root = flowRef.current
      if (!root) return
      const rootRect = root.getBoundingClientRect()
      const anchor = (key: string, side: 'left' | 'right') => {
        const el = nodeRefs.current.get(key)
        if (!el) return null
        const r = el.getBoundingClientRect()
        return { x: (side === 'left' ? r.left : r.right) - rootRect.left, y: r.top + r.height / 2 - rootRect.top }
      }
      const curve = (p1: { x: number; y: number }, p2: { x: number; y: number }) =>
        `M${p1.x} ${p1.y} C ${(p1.x + p2.x) / 2} ${p1.y} ${(p1.x + p2.x) / 2} ${p2.y} ${p2.x} ${p2.y}`
      const next: FlowLink[] = []
      clusters.forEach(c => c.tasks.forEach(t => {
        const p1 = anchor(`t:${t}`, 'right'), p2 = anchor(`c:${c.id}`, 'left')
        if (p1 && p2) next.push({ a: `t:${t}`, b: `c:${c.id}`, d: curve(p1, p2), color: getTaskColor(getTaskStatus(t)) })
      }))
      edits.forEach(e => e.clusters.forEach(cid => {
        const p1 = anchor(`c:${cid}`, 'right'), p2 = anchor(`e:${e.id}`, 'left')
        if (p1 && p2) next.push({ a: `c:${cid}`, b: `e:${e.id}`, d: curve(p1, p2), color: 'var(--primary)' })
      }))
      setLinks(next)
      setFlowSize({ w: root.scrollWidth, h: root.scrollHeight })
    }
    recompute()
    // jsdom (tests) has no ResizeObserver; the component still renders fine without
    // relayout-on-resize there.
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(recompute) : null
    if (ro && flowRef.current) ro.observe(flowRef.current)
    window.addEventListener('resize', recompute)
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', recompute)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusters, edits, taskGroups])

  const nodeKindOf = (prefixedId: string): 'task' | 'cluster' | 'edit' =>
    prefixedId[0] === 't' ? 'task' : prefixedId[0] === 'c' ? 'cluster' : 'edit'
  const endpointOn = (prefixedId: string) =>
    prefixedId === hoveredNode || isHighlighted(prefixedId.slice(2), nodeKindOf(prefixedId))
  const linkOpacity = (l: FlowLink) => (!hoveredNode ? 1 : endpointOn(l.a) && endpointOn(l.b) ? 1 : 0.08)

  // Tally counts
  const parentFailingTasks = [...tasksWith('fixed'), ...tasksWith('still_failing')]
  const parentFailing = parentFailingTasks.length
  const totalClusters = clusters.length
  const totalEdits = edits.length
  const fixed = tasksWith('fixed').length
  const brokeTasks = tasksWith('broke')
  const regressions = brokeTasks.length
  // "predicted" = the regressed task sits in one of the diagnosis's clusters
  const unpredictedRegressions = brokeTasks.filter(t => !taskToClusters.has(t)).length

  return (
    <div className="space-y-4">
      {edit?.hypothesis && (
        <div data-testid="edit-outcome" className="rounded-lg border p-3 text-sm"
          style={{ borderColor: outcome ? (outcome.moved ? 'var(--accepted)' : 'var(--rejected)') : 'var(--border)' }}>
          <div className="text-[10.5px] font-semibold uppercase tracking-wider text-[var(--muted)]">Edit hypothesis</div>
          <div className="mt-1">{edit.hypothesis}</div>
          {outcome && (
            <div className="tnum mt-2 text-xs text-[var(--muted-strong)]">
              target tasks: fixed {outcome.target.fixed}/{outcome.target.n}, broke {outcome.target.broke} · other tasks:
              fixed {outcome.rest.fixed}, broke {outcome.rest.broke}{' '}
              <strong style={{ color: outcome.moved ? 'var(--accepted)' : 'var(--rejected)' }}>
                {outcome.moved ? 'OUTCOME: target moved' : 'FLAG: edit did not move its target tasks'}
              </strong>
            </div>
          )}
        </div>
      )}
      {/* Validation warnings */}
      {diagnosis.warnings && diagnosis.warnings.length > 0 && (
        <div className="bg-[var(--failed)] bg-opacity-10 border border-[var(--failed)] border-opacity-30 rounded-lg p-3">
          <div className="text-sm font-semibold text-[var(--failed)] mb-2">Validation Warnings</div>
          <ul className="text-sm text-[var(--muted)] space-y-1">
            {diagnosis.warnings.map((w, i) => (
              <li key={i}>• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Headline */}
      {diagnosis.headline && (
        <div className="text-sm text-[var(--muted-strong)] leading-relaxed">{diagnosis.headline}</div>
      )}

      {/* Tally row */}
      <div className="flex gap-3 items-stretch flex-wrap">
        <div className="flex-1 min-w-[130px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
          <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-1">
            Parent failing
          </div>
          <div className="font-mono text-xl font-semibold">{parentFailing}</div>
          <div className="font-mono text-xs text-[var(--muted)] mt-1">tasks</div>
        </div>

        <div className="self-center text-[var(--muted)]">→</div>

        <div className="flex-1 min-w-[130px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
          <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-1">
            Clusters
          </div>
          <div className="font-mono text-xl font-semibold">{totalClusters}</div>
          <div className="font-mono text-xs text-[var(--muted)] mt-1">root causes</div>
        </div>

        <div className="self-center text-[var(--muted)]">→</div>

        <div className="flex-1 min-w-[130px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
          <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-1">
            Edits
          </div>
          <div className="font-mono text-xl font-semibold">{totalEdits}</div>
          <div className="font-mono text-xs text-[var(--muted)] mt-1">shipped</div>
        </div>

        <div className="self-center text-[var(--muted)]">→</div>

        <div className="flex-1 min-w-[130px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
          <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-1">
            Result
          </div>
          <div className="font-mono text-xl font-semibold text-[var(--accepted)]">{fixed}</div>
          <div className="font-mono text-xs text-[var(--muted)] mt-1">fixed</div>
        </div>

        <div className="self-center text-[var(--muted)]">→</div>

        <div className="flex-1 min-w-[130px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
          <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-1">
            Regressions
          </div>
          <div className="font-mono text-xl font-semibold text-[var(--rejected)]">{regressions}</div>
          <div className="font-mono text-xs text-[var(--muted)] mt-1">
            {unpredictedRegressions > 0 ? `${unpredictedRegressions} not predicted` : 'all predicted'}
          </div>
        </div>
      </div>

      {/* Three-column flow diagram: tasks ← root-cause clusters ← edits shipped, with
          curved links coloured by outcome (tasks→clusters) / primary (clusters→edits).
          Hovering any box traces its full connected path via isHighlighted/endpointOn. */}
      <div ref={flowRef} className="relative grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
        <svg
          className="hidden md:block absolute inset-0 pointer-events-none"
          style={{ width: flowSize.w || '100%', height: flowSize.h || '100%', overflow: 'visible' }}
        >
          {links.map(l => (
            <path
              key={`${l.a}->${l.b}`}
              d={l.d}
              fill="none"
              stroke={l.color}
              strokeWidth={1.6}
              strokeOpacity={0.55}
              opacity={linkOpacity(l)}
              style={{ transition: 'opacity 120ms' }}
            />
          ))}
        </svg>

        {/* Tasks column */}
        <div className="relative">
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Tasks ({parentFailing})
          </h3>
          <div className="space-y-2">
            {taskGroups.map(group => (
              <div key={group.key}>
                {group.label && (
                  <div className="text-[10.5px] text-[var(--muted)] mb-1">{group.label}</div>
                )}
                <div className="space-y-2">
                  {group.tasks.map(taskId => {
                    const status = getTaskStatus(taskId)
                    const highlighted = isHighlighted(taskId, 'task')
                    return (
                      <div
                        key={taskId}
                        ref={setNodeRef(`t:${taskId}`)}
                        className={`p-2 rounded border transition-all cursor-default ${
                          highlighted
                            ? 'border-[var(--fg)] bg-[var(--surface-3)]'
                            : 'border-[var(--border)] bg-[var(--surface-2)]'
                        }`}
                        onMouseEnter={() => setHoveredNode(`task:${taskId}`)}
                        onMouseLeave={() => setHoveredNode(null)}
                        style={{
                          borderLeftWidth: '3px',
                          borderLeftColor: getTaskColor(status),
                          opacity: endpointOn(`t:${taskId}`) ? 1 : hoveredNode ? 0.35 : 1,
                        }}
                      >
                        <div className="font-mono text-xs">{taskId}</div>
                        <div className="text-[10px] text-[var(--muted)] mt-0.5 uppercase">
                          {status.replace('_', ' ')}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Clusters column */}
        <div className="relative">
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Clusters ({totalClusters})
          </h3>
          <div className="space-y-2">
            {clusters.map(cluster => {
              const highlighted = isHighlighted(cluster.id, 'cluster')
              return (
                <div
                  key={cluster.id}
                  ref={setNodeRef(`c:${cluster.id}`)}
                  className={`p-2 rounded border transition-all cursor-default ${
                    highlighted
                      ? 'border-[var(--fg)] bg-[var(--surface-3)]'
                      : 'border-[var(--border)] bg-[var(--surface-2)]'
                  } ${cluster.latent ? 'border-dashed' : ''}`}
                  onMouseEnter={() => setHoveredNode(`cluster:${cluster.id}`)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ opacity: endpointOn(`c:${cluster.id}`) ? 1 : hoveredNode ? 0.35 : 1 }}
                >
                  <div className="flex items-start gap-2">
                    <span className="font-mono text-xs font-semibold text-[var(--primary)]">
                      {cluster.id}
                    </span>
                    <span className="text-xs flex-1">{cluster.name}</span>
                    {cluster.latent && (
                      <span className="text-[9px] text-[var(--muted)] uppercase border border-[var(--border)] rounded px-1">
                        latent
                      </span>
                    )}
                  </div>
                  {(cluster.tag || cluster.scope) && (
                    <div className="text-[10px] text-[var(--muted)] mt-1 uppercase">
                      {[cluster.tag, cluster.scope].filter(Boolean).join(' · ')}
                    </div>
                  )}
                  {cluster.detail && (
                    <div className="text-[11px] text-[var(--muted)] mt-1">{cluster.detail}</div>
                  )}
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {cluster.tasks.map(t => (
                      <span
                        key={t}
                        className="px-1.5 py-0.5 text-[9px] font-mono bg-[var(--surface)] rounded"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Edits column */}
        <div className="relative">
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Edits ({totalEdits})
          </h3>
          <div className="space-y-2">
            {edits.map(edit => {
              const highlighted = isHighlighted(edit.id, 'edit')
              return (
                <div
                  key={edit.id}
                  ref={setNodeRef(`e:${edit.id}`)}
                  className={`p-2 rounded border transition-all cursor-default ${
                    highlighted
                      ? 'border-[var(--fg)] bg-[var(--surface-3)]'
                      : 'border-[var(--border)] bg-[var(--surface-2)]'
                  }`}
                  onMouseEnter={() => setHoveredNode(`edit:${edit.id}`)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ opacity: endpointOn(`e:${edit.id}`) ? 1 : hoveredNode ? 0.35 : 1 }}
                >
                  <div className="flex items-start gap-2">
                    <span className="font-mono text-xs font-semibold text-[var(--accent)]">
                      {edit.id}
                    </span>
                    <span className="text-xs flex-1">{edit.title}</span>
                  </div>
                  {(edit.lever || edit.blast_radius) && (
                    <div className="text-[10px] text-[var(--muted)] mt-1">
                      {[edit.lever, edit.blast_radius].filter(Boolean).join(' · ')}
                    </div>
                  )}
                  {edit.verified && (
                    <div className="text-[11px] text-[var(--muted)] mt-1">{edit.verified}</div>
                  )}
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {(edit.files ?? []).map(f => (
                      <span
                        key={f}
                        className="px-1.5 py-0.5 text-[9px] font-mono bg-[var(--surface)] rounded"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {edit.clusters.map(c => (
                      <span
                        key={c}
                        className="px-1.5 py-0.5 text-[9px] font-mono bg-[var(--primary)] bg-opacity-20 text-[var(--primary)] rounded"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Skipped edits */}
      {skipped.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Skipped edits ({skipped.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {skipped.map((s, i) => (
              <div
                key={i}
                className="p-3 rounded border border-dashed border-[var(--border-strong)] bg-[var(--surface-2)]"
              >
                <div className="text-sm font-semibold mb-1">{s.title}</div>
                <div className="text-xs text-[var(--muted)]">{s.reason}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {diagnosis.note && (
        <div className="text-xs text-[var(--muted)]">Note: {diagnosis.note}</div>
      )}

      {/* Techniques */}
      {diagnosis.techniques && diagnosis.techniques.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold mb-2 text-[var(--muted-strong)]">Techniques used</h3>
          <div className="flex gap-2 flex-wrap">
            {diagnosis.techniques.map((t, i) => (
              <span
                key={i}
                className="px-2 py-1 text-xs rounded bg-[var(--surface-2)] border border-[var(--border)]"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
