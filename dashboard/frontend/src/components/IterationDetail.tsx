import { useState } from 'react'
import type { GraphNode, GateDecision, RunSummaryDetail } from '../lib/types'
import { GatePanel } from './GatePanel'
import { TaskMatrix } from './TaskMatrix'
import { IterationsDiff } from './IterationsDiff'
import { DiagnosisFlow } from './DiagnosisFlow'
import { PromptMap } from './PromptMap'
import { VerdictBadge } from './StatusBadge'

interface IterationDetailProps {
  iteration: number
  candidate: GraphNode
  parent: GraphNode | null
  gate: GateDecision | null
  runId: string
  onClose: () => void
}

type TabId = 'overview' | 'diagnosis' | 'prompt-map' | 'tasks' | 'gate' | 'diff' | 'process'

export function IterationDetail({
  iteration,
  candidate,
  parent,
  gate,
  runId,
  onClose,
}: IterationDetailProps) {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  const hasPromptMap = !!candidate.prompt_map

  const tabs: Array<{ id: TabId; label: string; enabled: boolean }> = [
    { id: 'overview', label: 'Overview', enabled: true },
    { id: 'diagnosis', label: 'Optimizer · diagnosis', enabled: true }, // Always show, with fallback
    { id: 'prompt-map', label: 'Prompt map', enabled: hasPromptMap },
    { id: 'tasks', label: 'Evaluation · tasks', enabled: !!candidate.per_task },
    { id: 'gate', label: 'Gate decision', enabled: !!gate },
    { id: 'diff', label: 'Changes (diff)', enabled: !!parent },
    { id: 'process', label: 'PROCESS.md', enabled: true },
  ]

  const formatPercent = (v: number | null | undefined) => {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`
  }

  const formatUsd = (v: number | null | undefined, metered: boolean = true) => {
    if (v == null) return '—'
    if (!metered || v === 0) return '—'
    return `$${v.toFixed(4)}`
  }

  const formatTokens = (v: number | null | undefined) => {
    if (v == null) return '—'
    return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}K` : String(v)
  }

  const formatDuration = (seconds: number | null | undefined) => {
    if (!seconds) return '—'
    const s = Math.round(seconds)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg mt-4">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--border)]">
        <h2 className="text-lg font-semibold">Iteration {iteration}</h2>
        <span className="px-2 py-1 text-xs rounded bg-[var(--surface-2)] border border-[var(--border)] font-mono">
          {candidate.id}
        </span>
        {gate && <VerdictBadge verdict={gate.verdict || candidate.status} />}
        <button
          onClick={onClose}
          className="ml-auto px-3 py-1 text-sm bg-[var(--surface-2)] border border-[var(--border)] rounded hover:border-[var(--border-strong)] transition-colors"
        >
          Close
        </button>
      </div>

      {/* Subtitle */}
      {parent && (
        <div className="px-5 py-2 text-sm text-[var(--muted)]">
          from {parent.id} · {formatPercent(parent.val)} → {formatPercent(candidate.val)} (Δ{' '}
          {candidate.val != null && parent.val != null
            ? (candidate.val - parent.val >= 0 ? '+' : '') + (candidate.val - parent.val).toFixed(3)
            : '—'}
          )
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] px-3 overflow-x-auto">
        {tabs
          .filter(t => t.enabled)
          .map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2.5 text-[13.5px] border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'text-[var(--fg)] border-[var(--primary)]'
                  : 'text-[var(--muted)] border-transparent hover:text-[var(--fg)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
      </div>

      {/* Tab content */}
      <div className="p-5">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Flow: parent → optimizer → candidate → eval → gate */}
            <div className="flex items-stretch gap-0 flex-wrap">
              {parent && (
                <>
                  <div className="flex-1 min-w-[150px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                    <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-2">
                      Parent
                    </div>
                    <div className="font-mono text-base font-semibold mb-1">{parent.id}</div>
                    <div className="font-mono text-xs text-[var(--muted)]">
                      val {formatPercent(parent.val)}
                    </div>
                  </div>
                  <div className="flex items-center px-2 text-[var(--muted)]">→</div>
                </>
              )}

              <div className="flex-1 min-w-[150px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-2">
                  Optimizer
                </div>
                <div className="font-mono text-base font-semibold mb-1">
                  {formatDuration(candidate.optimizer_seconds)}
                </div>
                <div className="font-mono text-xs text-[var(--muted)]">
                  {formatUsd(candidate.opt_cost_usd)} · {formatTokens(candidate.opt_tokens)} tok
                </div>
              </div>

              <div className="flex items-center px-2 text-[var(--muted)]">→</div>

              <div className="flex-1 min-w-[150px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-2">
                  Candidate
                </div>
                <div className="font-mono text-base font-semibold mb-1">{candidate.id}</div>
                <div className="font-mono text-xs text-[var(--muted)]">
                  {candidate.diagnosis?.headline || 'no diagnosis'}
                </div>
              </div>

              <div className="flex items-center px-2 text-[var(--muted)]">→</div>

              <div className="flex-1 min-w-[150px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-2">
                  Evaluation
                </div>
                <div className="font-mono text-base font-semibold mb-1">
                  {formatPercent(candidate.val)}
                </div>
                <div className="font-mono text-xs text-[var(--muted)]">
                  ± {candidate.stderr?.toFixed(3) || '—'} · {formatDuration(candidate.runner_seconds)}
                </div>
              </div>

              {gate && (
                <>
                  <div className="flex items-center px-2 text-[var(--muted)]">→</div>
                  <div className="flex-1 min-w-[150px] bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                    <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold mb-2">
                      Gate
                    </div>
                    <div className="font-mono text-base font-semibold mb-1">
                      {gate.verdict.toUpperCase()}
                    </div>
                    <div className="font-mono text-xs text-[var(--muted)]">
                      Δ {gate.delta?.toFixed(4) || '—'} vs {gate.threshold?.toFixed(4) || '—'}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Fixed
                </div>
                <div className="font-mono text-lg font-semibold mt-1.5">
                  {candidate.fixed?.length || 0}
                </div>
                <div className="font-mono text-xs text-[var(--muted)] mt-1">
                  vs {parent?.id || 'parent'}
                </div>
              </div>

              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Broke
                </div>
                <div className="font-mono text-lg font-semibold mt-1.5">
                  {candidate.broke?.length || 0}
                </div>
                <div className="font-mono text-xs text-[var(--muted)] mt-1">
                  regressions
                </div>
              </div>

              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Tokens
                </div>
                <div className="font-mono text-lg font-semibold mt-1.5">
                  {formatTokens(candidate.tokens)}
                </div>
                <div className="font-mono text-xs text-[var(--muted)] mt-1">
                  opt {formatTokens(candidate.opt_tokens)}
                </div>
              </div>

              <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-3">
                <div className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Cost
                </div>
                <div className="font-mono text-lg font-semibold mt-1.5">
                  {candidate.cost_usd != null && candidate.cost_usd > 0 ? formatUsd(candidate.cost_usd) : '—'}
                </div>
                <div className="font-mono text-xs text-[var(--muted)] mt-1">
                  opt {candidate.opt_cost_usd != null && candidate.opt_cost_usd > 0 ? formatUsd(candidate.opt_cost_usd) : '—'}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'diagnosis' && (
          <>
            {candidate.diagnosis ? (
              <DiagnosisFlow diagnosis={candidate.diagnosis} outcomes={candidate.outcomes} />
            ) : (
              <div className="space-y-4">
                <div className="text-sm text-[var(--muted)]">
                  No structured diagnosis available for this iteration.
                </div>
                
                {/* Show outcomes data if available */}
                {candidate.outcomes && (
                  <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-4">
                    <h3 className="text-sm font-semibold mb-3">Task Outcomes vs Parent</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div>
                        <div className="text-xs text-[var(--muted)] mb-1">Fixed</div>
                        <div className="font-mono text-lg font-semibold text-[var(--accepted)]">
                          {candidate.outcomes.fixed?.length || 0}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--muted)] mb-1">Broke</div>
                        <div className="font-mono text-lg font-semibold text-[var(--rejected)]">
                          {candidate.outcomes.broke?.length || 0}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--muted)] mb-1">Still Failing</div>
                        <div className="font-mono text-lg font-semibold text-[var(--failed)]">
                          {candidate.outcomes.still_failing?.length || 0}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--muted)] mb-1">Still Passing</div>
                        <div className="font-mono text-lg font-semibold">
                          {candidate.outcomes.still_passing?.length || 0}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Link to PROCESS.md */}
                <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-4">
                  <p className="text-sm mb-2">
                    For optimizer reasoning, see the{' '}
                    <button
                      onClick={() => setActiveTab('process')}
                      className="text-[var(--primary)] hover:underline"
                    >
                      PROCESS.md tab
                    </button>
                    .
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'prompt-map' && candidate.prompt_map && (
          <PromptMap promptMap={candidate.prompt_map} candidateId={candidate.id} runId={runId} />
        )}

        {activeTab === 'tasks' && candidate.per_task && (
          <div>
            <div className="mb-4 text-sm text-[var(--muted)]">
              Task results for {candidate.id} vs {parent?.id || 'parent'}
            </div>
            <TaskMatrix
              summary={{ tasks: Object.keys(candidate.per_task) } as RunSummaryDetail}
              nodes={parent ? [parent, candidate] : [candidate]}
              selectedId={null}
            />
          </div>
        )}

        {activeTab === 'gate' && gate && (
          <GatePanel
            summary={{ gate_decisions: [gate] } as RunSummaryDetail}
            nodes={parent ? [parent, candidate] : [candidate]}
          />
        )}

        {activeTab === 'diff' && parent && (
          <IterationsDiff
            runId={runId}
            graph={{ nodes: parent ? [parent, candidate] : [candidate], root: parent?.id || candidate.id, best_id: candidate.id }}
          />
        )}

        {activeTab === 'process' && (
          <div className="prose prose-sm max-w-none">
            <div className="text-sm text-[var(--muted)] mb-4">
              PROCESS.md for {candidate.id}
            </div>
            <div className="bg-[var(--surface-2)] border border-[var(--border)] rounded-lg p-4 max-h-[600px] overflow-auto">
              <p className="text-[var(--muted)]">
                PROCESS.md content would be loaded from /api/runs/{runId}/candidate/{candidate.id}/files
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
