# cap-evolve subagent patterns

Two subagents ship with the plugin; both are optional accelerators. The pipeline
runs without them (the host-agnostic `run-optimizer` headless path covers the same
ground sequentially), but inside Claude Code they unlock parallel fan-out and a
clean read/write privilege split.

| agent | privilege | model | role |
|---|---|---|---|
| `cap-evolve-diagnoser` | read-only (`Read, Grep, Glob, Bash`) | sonnet | turn failing val rollouts + traces into a reflective dataset |
| `cap-evolve-proposer` | writing (`Read, Write, Edit, Grep, Glob, Bash`) | opus | apply ONE targeted edit to a candidate working copy |

## Why the split
Diagnosis is read-only by construction, so it is **safe to run many at once** and
cheap to fork. Proposal writes, so it runs **one at a time per candidate** and on a
stronger model. Keeping them separate means a diagnoser can never accidentally
mutate state, and the writing step is small and auditable.

## Parallel diagnose fan-out
The diagnose phase (and GEPA's per-minibatch reflection) is embarrassingly
parallel across tasks/clusters:

```
for each failing-task cluster (or minibatch shard):
    fork cap-evolve-diagnoser  (context: fork, read-only)  ──┐
                              ...                            ├─ run concurrently
    fork cap-evolve-diagnoser                              ──┘
join → merge per-cluster reflective datasets → one REFLECTION.md
```

A phase skill triggers this by declaring `context: fork` + `agent:
cap-evolve-diagnoser` in its frontmatter, or the orchestrator dispatches several
diagnoser subagents in a single turn (independent tasks, no shared state) and
merges their JSON outputs.

## Parallel evaluate fan-out
Evaluation is also parallel: each (candidate, task, trial) rollout is independent.
The engine's backend protocol allocates a separate candidate dir per evaluation
(`allocate_candidate_dir`), so multiple rollouts run without colliding on a single
live slot. Fan out rollouts, then reduce to per-task mean ± SE for the gate.

## Sequential proposer
Proposal is **not** fanned out per candidate: one edit per iteration keeps the
diff attributable and the lineage a tree. Across *different* frontier parents the
proposer may run in parallel (distinct working copies), but never two proposers on
the same candidate.

## Honesty boundary
Both agents are reminded in their own prompts, and the PreToolUse hook enforces
it regardless: no edits to `splits.json`, `rollouts/test/*`, or `*test*gold*`
files; the diagnoser never reads the test split. Enforcement lives in
core-owned hook scripts, not in these editable agent files.
