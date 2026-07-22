# The two graphs, branches, and solutions

EvoGraph keeps two mutually-linked graphs under `<run_dir>/wiki/`:

- **Weaknesses** (`wiki/weaknesses/<slug>.md`) — what's broken. Persistent across rounds; shrinks (in
  active count) as weaknesses get stamped `solved`.
- **Solutions** (`wiki/solutions/<weakness-slug>/<sol-id>/`) — a kept improvement (it raised the
  weakness's task average). Grows monotonically. Dead ends never become solutions — they go to the
  weakness's RSM.

Every solution `[[wikilink]]`s back to its weakness; every weakness lists its solutions. The
dashboard graph shows **weaknesses only** (connected by their `related` links — see
[clustering.md](clustering.md)); solutions appear inside a weakness's detail panel.

## Absolute wiki path (most important rule)

Every teammate gets the wiki as an **absolute** path: `<run_dir>/wiki/`. Solvers run in their
own worktrees — a relative `./<run_dir>/wiki/` would point at the worktree's private copy, invisible
to everyone else and to the dashboard. Always write to the absolute path.

## Branch model

- The lead creates the `evograph` branch up front **and a root worktree at `<run_dir>/root`** checked
  out on it — *all* of EvoGraph's work happens there, so the user's original checkout is never
  modified. All accepted fixes land on `evograph` (never on the user's branch unless they ask).
- When a weakness is first attacked, give it a **weakness branch** off `evograph` (e.g.
  `evograph/w/<slug>`); record it in the weakness md `branch:` field.
- A solver works in its own **worktree** (under `<run_dir>/worktrees/`) on a solution branch off the
  weakness branch. The shared wiki stays in `<run_dir>/wiki/` (absolute path), outside every
  worktree.

## Solution layout

`wiki/solutions/<weakness-slug>/<sol-id>/`, where **sol-id = `r<N>-h<M>`**: `r<N>` is the **round**
the attempt was made in, and `h<M>` is the **hypothesis (attempt) index** within that weakness —
`h1` is the first fix tried, `h2` the second, and so on. So `r2-h3` = the third hypothesis tried for
this weakness, made in round 2.

- `solution.md`
- `changes.diff` — captured **before** requesting merge:
  `git diff <weakness-branch-base>..<solution-HEAD>`. Snapshotting here keeps the UI's diff stable
  even after later commits land on the weakness branch.

Example `solution.md` (front-matter + body) — this is a **solution** file, not the weakness node
(the weakness `<slug>.md` schema lives in [clustering.md](clustering.md)):

```markdown
---
weakness: "[[tool-call-arg-mismatch]]"
round: 1
attempt_index: 1            # the h<M>
branch: evograph/w/tool-call-arg-mismatch/h1
timestamp: 2026-06-28T14:03:00+03:00   # from `python scripts/now.py` — never hand-written
outcome: kept               # pending while in-flight → kept once re-eval confirms it improved (dead ends aren't solutions)
tags: [tool-calling]
primary_metric: { name: reward, value: 0.74 }
secondary_metrics: [ { name: avg_steps, value: 12.1 } ]
new_record: true            # set true if this beat the weakness's previous best on its tasks
---

# Validate tool-call arg types in the planner

## Thesis
One line: the idea for resolving the weakness.

## Reasoning / approach
A paragraph: why this should work, given what the trajectories show.

## Change list
- `agent/planner.py` — coerce arg types against the tool schema before dispatch.

## Per-task metric delta (weakness tasks)
| task    | before | after | Δ    |
|---------|--------|-------|------|
| task_007| 0.0    | 1.0   | +1.0 |
| task_011| 0.4    | 0.4   |  0.0 |

## Baseline comparison
Kept iff the **average primary metric across all the weakness's `affected_tasks`** rises vs the
prior best (equivalently, net Δ > 0 over that fixed task set — not just one task improving). With
trials-per-task, each task's score is itself the mean over its trials.

## References
- `agent/planner.py:88`

See also [[tool-call-arg-mismatch]].
```

Pre-write `solution.md` with `outcome: pending` before editing code, so intent survives a crash;
finalize `outcome` + metrics + `new_record` after the verified re-eval.

## Don't break the neighbors — use the graph edges

The graph's **edges live on the weakness node, not on the solution.** Each
`wiki/weaknesses/<slug>.md` lists `related:` neighbors (`slug` + `why`) — those are exactly the
edges the dashboard draws (schema in [clustering.md](clustering.md)). A solution file only links
*up* to its own weakness via `weakness: [[…]]`.

A weakness's `related` neighbors are the fix's **blast radius — stay aware of them, don't re-run
them.** A fix kept on W's own task average can quietly regress a connected weakness V, so avoid
changes that obviously undermine W's neighbors and note any likely cross-weakness impact in the
solution body. The **round-start eval** is the backstop for a real regression.

## PR / merge

- **Only the lead merges.** The lead **trusts the solver's reported result** — the solver already
  re-evaluated the fix on its **own weakness's tasks** during research — so it does *not* re-run the
  eval per fix; it merges into `evograph` one weakness at a time and resolves conflicts. The
  whole-train **round-start eval** (see below) is the objective backstop that catches anything wrong.
- The route is set by the **`github_integration`** choice captured at setup by cap-evolve
  `intake` and recorded in the project spec (`capevolve.yaml`):
- **`github_integration: true`** (GitHub CLI authenticated and the user opted in) → GitHub **mirrors**
  the wiki, which stays the source of truth (it's what the UI reads). At PR time the solver **syncs
  the weakness's GitHub issue to match its weakness md**, then opens a **PR** explaining the
  auto-research + measured gain, with `Closes #<n>`; the lead reviews/merges.
- **`github_integration: false`** (not authenticated, or the user opted to keep it local) → no GitHub
  issue/PR; the solver asks the lead to merge the branch directly.

## Per-round tags + whole-round revert

The lead drives the round loop, and round-over-round it guards against regressions:

- **Tag the round's starting tip.** At the start of round N, *before* that round's merges land, the
  lead tags the current evograph tip: `git -C <run_dir>/root tag -f evograph-round-<N>-start`.
  This tip is the state the round's start-eval measures (everything merged through round N−1).
- **Detect regression.** The start-of-round-N eval reflects round N−1's merges. If round N's
  **primary metric** is below round N−1's, round N−1's combined merges regressed the suite.
- **Revert the whole round.** `git -C <run_dir>/root reset --hard evograph-round-<N-1>-start` rolls
  back to the tip *before* round N−1's merges, then re-eval to confirm the baseline is restored.
  Whole-round revert is deliberately coarse: even a single bad merge rolls back all of that round's
  fixes, and the reverted weaknesses get re-attacked next round.
- **Sign the graph.** Every weakness in round N−1's `attacked_in_rounds` flips to status
  `reverted` (dashboard renders it distinctly; it is eligible to be attacked again), gains the round
  in `reverted_in_rounds`, and gets an RSM note: `round N−1 combined fixes regressed primary X→Y —
  rolled back`. Their round-N−1 solution files are **demoted into RSM with their metrics + branch** —
  a reverted attempt is not a kept solution, so it must not stay under `wiki/solutions/`.
