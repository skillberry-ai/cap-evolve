---
name: evograph
description: >-
  Deprecated agent-mode algorithm (evo-graph port): a weakness-graph search that dispatched one
  solver agent per failure cluster and reverted a whole round on regression. Do not start new runs
  with it — its per-weakness fan-out is already `agent-optimize`'s sibling fan-out, done behind the
  honest val significance gate that evograph never applied, and everything else it did (failure
  clustering, rejected-edit memory, budget-aware fan-out, free-text stop condition) lives in
  `agent-optimize` + `phases/diagnose`. Use when reading or repairing an existing evograph run dir,
  or when writing the run-dir `wiki/` format the dashboard's Weakness-graph tab reads — and to see
  what to select instead: `agent-optimize` for agent-mode search, `hill-climb`, `gepa`, or
  `skillopt` for a deterministic loop.
component: algorithm
argument-hint: "deprecated — use agent-optimize (agent mode) or hill-climb | gepa | skillopt"
allowed-tools: Read, Write, Edit, Bash, Task
needs: [scores, traces, candidate]
provides: [candidate]
sources: [evo-graph]
---

# evograph — DEPRECATED

**Do not select `algorithm_skill: evograph` for a new run.** Use `agent-optimize` (agent mode) or
`hill-climb` / `gepa` / `skillopt` (deterministic) with `memory_skill: wiki` if you want THIS run's
weakness-graph format. This file stays so an existing evograph run dir is still readable.

## Why it is deprecated

evograph advertised one distinctive capability — a collaborative weakness graph with one solver
agent per weakness, merged into a shared candidate each round. Measured against its four siblings,
that capability is not distinctive and the part that *was* distinctive was a defect:

- **The fan-out already exists, gated properly.** `agent-optimize` fans out N sibling candidates
  from the same parent, one diagnosed failure cluster each, every sibling in its own working copy
  (a git worktree when the capability is in git), gated **one at a time with a re-gate after each
  accept** so several fixes accumulate into one lineage honestly. That is evograph's round, minus
  the flaws below. The clustering itself is `phases/diagnose`'s job in both cases.
- **Acceptance was never held out.** evograph kept a merge on a raw delta over a frozen 3-task
  subset of *train*, self-reported by the solver subagent that made the edit — no val split, no
  standard error, no `Δ > k·SE`. Between `baseline` and `finalize` an evograph run took no
  held-out measurement at all, so the sealed test number was the first honest signal anyone saw.
  Whole-round revert existed only as a one-round-late substitute for the gate it lacked; wire the
  real gate and there is nothing left for it to catch.
- **What remains unique is an output format, not a search strategy.** The run-dir `wiki/` is
  genuinely useful, but the dashboard renders the Weakness-graph tab from `wiki/` presence alone,
  for any algorithm that writes the format (`core/cap_evolve/dashboard.py`). An output contract
  does not earn a second agent-mode algorithm that users must choose between — it has since moved
  to `skills/memory/wiki/SKILL.md`, a standalone `memory_skill` any algorithm can select (#400,
  #404), so it no longer needs evograph to stay alive.

## There is no deterministic engine

There never was one, and `scripts/run.py` is a tombstone, not a stub: invoked deterministically it
exits 2 with an `agent-mode only` payload rather than faking a loop. So evograph is also the one
algorithm that could not be routed through the shared per-iteration record — see
the `hill-climb` skill's `references/run-step.md`, which owns the shared iteration mechanics
(parent selection, val gate, commit, iteration record) every other algorithm routes through. Read
it if you are reconstructing what an evograph round *should* have done.

## Reading an existing evograph run

The run dir is authoritative. `<run_dir>/wiki/` holds the weakness nodes, solution cards and
per-round results; `<run_dir>/runs/round-<N>/agents/<slug>.log` holds solver progress. The formats
are in [references/dashboard.md](references/dashboard.md) — load it if you need to write or parse
that wiki. Treat any per-weakness "kept / new record" number in it as a train-subset self-report,
not a gated result; only `finalize`'s sealed test number and any `gate` decision recorded in
`events.jsonl` are honest.

`scripts/now.py` is the one-clock timestamp stamper those formats require; it is correct and still
used by anything writing the wiki.

## Removal is a separate decision

Deprecation is reversible; removal is not. The wiki format contract now has a real owner
(`skills/memory/wiki/SKILL.md`), so what's left to decide (maintainer): stop `dashboard.py`
inferring `algorithm = "evograph"` from `wiki/` presence alone (any `memory_skill: wiki` run now
writes it too), then delete this directory.

## References
- [skills/memory/wiki/SKILL.md](../../memory/wiki/SKILL.md) — the wiki format contract's current
  home: weakness-node/solution-card schemas, generalized for any algorithm via `memory_skill: wiki`.
- [references/dashboard.md](references/dashboard.md) — the same file formats, kept here for reading
  an existing evograph run dir's branch/round-revert specifics the generalized skill dropped.
- [references/clustering.md](references/clustering.md) — weakness-node schema and the
  `affected_tasks` freeze rule, kept for reading historical run dirs.
- [references/graph.md](references/graph.md) — solution-card schema, branch layout, whole-round
  revert, kept for the same reason.
