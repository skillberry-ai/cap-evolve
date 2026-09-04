---
name: wiki
description: >-
  Cross-iteration memory as a weakness graph (weakness nodes + solution cards), extracted
  from the deprecated `evograph` algorithm's run-dir format per its own maintainer note.
  Select via `memory_skill: wiki` in capevolve.yaml (default is `md-files`). Copied into
  every iteration's working dir as `./guidance/memory-wiki/` when selected; read this
  before writing anything under the run dir's `wiki/`.
component: memory
argument-hint: "no direct invocation — selected via memory_skill: wiki in capevolve.yaml"
allowed-tools: Read, Write, Edit
sources: [evo-graph, evograph]
---

# memory-wiki — the weakness graph memory format

This is a memory FORMAT, not a search strategy: any algorithm (hill-climb, gepa, skillopt,
agent-optimize) can select `memory_skill: wiki` and get this instead of the default
`md-files` (LEDGER/JOURNAL/PROCESS/INSIGHTS). It replaces per-iteration append-only prose
with a **persistent graph of known weaknesses**, each carrying its own history of what was
tried and what worked — read once, re-read every iteration, useful across the whole run
instead of scrolling a growing journal.

## Absolute path (most important rule)

Write to `<run_dir>/wiki/` — the **absolute path**, never a relative copy inside your
per-iteration working dir. Every iteration gets a fresh working copy; the wiki does not
live inside it and is never copied in or folded back. Writing to the absolute path is what
makes it visible to the next iteration (and to the dashboard's Weakness-graph tab, which
reads `wiki/` straight out of the run dir).

## The two graphs

- **Weaknesses** (`wiki/weaknesses/<slug>.md`) — what's broken. Persistent across
  iterations; a weakness's `related` neighbors are the graph's edges.
- **Solutions** (`wiki/solutions/<weakness-slug>/<sol-id>/`) — a kept improvement for one
  weakness. Every solution `[[wikilink]]`s back to its weakness.

### Weakness node — `wiki/weaknesses/<slug>.md`

```markdown
---
slug: tool-call-arg-mismatch
status: in-progress            # open | in-progress | completed | solved | reverted
tags: [tool-calling, type-error]
discovered_in_iteration: cand_0003
attacked_in_iterations: [cand_0003, cand_0007]
solved_in_iteration: null
affected_tasks: [task_007, task_011, task_023]   # FROZEN after discovery — see below
related:
  - slug: schema-drift-after-retry
    why: both corrupt the tool-call payload; candidates to merge
solutions:
  - "[[tool-call-arg-mismatch-cand_0007]]"
---

# Tool call arg mismatch

## What fails
The agent's tool-call planner passes a dict where the tool expects a string.

## Tasks (found on)
- task_007 — search query sent as JSON object

## References
- `agent/planner.py:88` — builds the args dict; no type coercion before dispatch.

## Rejected Store Memory (RSM)
(Empty at discovery; append dead-end attempts here so a later iteration does not retry them.)
```

**Freeze rule**: `affected_tasks` may only grow in the weakness's discovery iteration —
after that it is frozen, because solutions are scored against that exact task set and
changing it invalidates the comparison. Only `status` may change afterward.

**RSM entry** (append-only, inside the weakness md, one per rejected attempt):
```markdown
### <iteration id> · <rejected-direction-slug>
- **Thesis**: one line
- **Change**: files touched, summarized
- **Metrics (weakness tasks)**: <primary metric> <value>
- **Why rejected**: dead end (no gain) · or reverted (broke another task)
```

### Solution card — `wiki/solutions/<weakness-slug>/<sol-id>/{solution.md,changes.diff}`

`sol-id` is the candidate id that produced it (e.g. `cand_0007`).

```markdown
---
weakness: "[[tool-call-arg-mismatch]]"
iteration: cand_0007
outcome: kept               # pending -> kept once the gate confirms it improved
timestamp: 2026-06-28T14:03:00+03:00   # python scripts/now.py — never hand-written
primary_metric: { name: reward, value: 0.74 }
new_record: true            # true if this beat the weakness's previous best on its tasks
---

# Validate tool-call arg types in the planner

## Thesis
One line: the idea for resolving the weakness.

## Change list
- `agent/planner.py` — coerce arg types against the tool schema before dispatch.

## Per-task metric delta (weakness tasks)
| task    | before | after | Δ    |
|---------|--------|-------|------|
| task_007| 0.0    | 1.0   | +1.0 |

See also [[tool-call-arg-mismatch]].
```

`changes.diff` — the capability diff for this candidate vs its parent (the framework's own
`diff.patch`/LEDGER already have this; keep `changes.diff` as a wiki-local copy so a reader
of the weakness graph never has to leave it).

**Acceptance is never self-reported here.** `outcome`/`new_record` reflect the SAME honest
val-significance gate every memory scheme reports through (`LEDGER.md`, framework-owned,
also written under this scheme) — write the solution card once the candidate is actually
accepted, not before.

### Per-iteration metrics → `wiki/results/round-<N>.json`

```json
{
  "round": 1,
  "split": "val",
  "started_at": "2026-06-28T14:00:00+03:00",
  "completed_at": "2026-06-28T14:04:12+03:00",
  "metrics": { "reward": { "value": 0.62, "primary": true, "direction": "higher" } },
  "per_task": [ { "task_id": "0", "reward": 1.0 } ]
}
```

Every metric is the wrapped object `{ value, primary, direction }`, never a flat number —
the dashboard's timeline reads `.value`. Stamp `started_at`/`completed_at` from
`python scripts/now.py` so every file agrees on the clock.

## What the dashboard renders

The dashboard's Weakness-graph tab reads `wiki/` directly out of the run dir: one row per
weakness (`status`, `tags`, `related` edges, solution count), the primary metric over
`wiki/results/round-<N>.json`, and each solution's diff. No registration, no API — write
the files in this format and the viewer reflects them within a couple of seconds. Everything
in these files the dashboard doesn't recognize is preserved and ignored, so extra keys are
always safe.

## What this format does NOT give you

Whole-round revert, branches/worktrees-per-weakness, and multi-builder distribution were
`evograph`'s ALGORITHM (its search strategy, now deprecated — see
`skills/algorithms/evograph/SKILL.md`), not this FORMAT. Selecting `memory_skill: wiki` with
any algorithm gets you the graph and its file contract; the val-significance gate, git
history and accept/reject mechanics stay whatever that algorithm already does.
