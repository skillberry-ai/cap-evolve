# Building the weakness graph (clustering)

The weakness wiki is the team's **shared state**. Builders write it **directly** — there are no
intermediate draft files. This is the "parallel cartography on a shared graph" idea: many agents grow
one graph at once.

## The flow

1. After the round's eval, the failed tasks (score < max) are the starting point. **Distribute them
   across however many builders makes sense** for the failure volume and the harness — your call.
   Just split **by whole task id** (never split one task's trajectory across builders) so each builder
   sees full context per task. **Don't look at failures only** — builders should also read the
   **successful** trajectories (if bench has trials-per-task a task often passes on some trials and fails on
   others); contrasting pass vs fail for the same task is what reveals the cause.
2. Each builder reads its slice + the existing weaknesses, then for each failure that hurts the
   primary metric:
   - **Search** `wiki/weaknesses/` for a matching pattern.
   - **Match** → append/extend that weakness file (broaden "What fails", add a trajectory excerpt and
     a reference). Add tasks **only if it's that weakness's discovery round** (freeze rule below).
   - **No match** → create a new `wiki/weaknesses/<slug>.md` with `status: open`.
3. The lead does a light **dedup pass — only over weaknesses newly coined this round**: if two
   builders created near-duplicate slugs for the same pattern, merge them (pick a canonical slug, fold
   the other's tasks/excerpts in). Leave established weaknesses (those already carrying
   history/solutions/frozen tasks) alone.

A weakness is *anything* that keeps the primary metric below its max — including **inconsistency**: a
task that sometimes passes and sometimes doesn't is a real weakness (a consistency problem), not a
pass.

## Freeze rule

`affected_tasks` may grow **only in the weakness's discovery round**. After that, it's frozen:
solutions have already been scored against that exact task set, and changing it would invalidate
those comparisons and the "new record" signal. In later rounds you may only change `status`:
`open`/`completed`/`reverted` → `in-progress` when re-attacked → `completed` (shipped an
improvement, stopped) or `solved` (tasks now all ~perfect); a recurring `solved` weakness can go back
to `in-progress`; a whole-round revert flips every weakness attacked that round to `reverted` (see
[graph.md](graph.md)). Add each attack round to `attacked_in_rounds`.

## Related weaknesses

When a weakness clearly relates to another (same root cause, overlapping fix), add it to `related`
with a one-line `why`. The dashboard draws these as edges, so the graph reflects how failures cluster.
If two `related` weaknesses look like the *same* problem, you may **merge them — but only while both
are in their discovery round** (folding one's tasks into the other). After that the freeze rule
applies: their task sets are pinned to existing solutions, so leave them linked rather than merged.

## Concurrency (light, no heavy locks)

Builders write different files almost always. To avoid two builders editing the *same* file at once,
announce the slug you're about to touch on the shared task list before writing it; if someone else
holds it, hand them your finding instead. The lead's dedup pass cleans up the rare collision. Don't
build a locking protocol — keep it light.

## Canonical weakness file

```markdown
---
slug: tool-call-arg-mismatch
status: in-progress            # open | in-progress | completed | solved | reverted
tags: [tool-calling, type-error]
discovered_in_round: 1
attacked_in_rounds: [1, 2]
solved_in_round: null
reverted_in_rounds: []         # rounds whose merged fix was rolled back by a whole-round revert
branch: evograph/w/tool-call-arg-mismatch   # the weakness's worktree branch (set when first attacked)
affected_tasks: [task_007, task_011, task_023]   # FROZEN after discovery round
related:                                     # optional — graph edges; also the fix's blast-radius watchlist (see graph.md)
  - slug: schema-drift-after-retry
    why: both corrupt the tool-call payload; candidates to merge
solutions:
  - "[[tool-call-arg-mismatch-r1-h1]]"
---

# Tool call arg mismatch

## What fails
The agent's tool-call planner passes a dict where the tool expects a string → `ToolError`.

## Tasks (found on)
- task_007 — search query sent as JSON object — `runs/round-1/...:42`
- task_011 — ...

## Trajectory excerpts
> Tool call: search(query={"q": "..."}) → ToolError: expected str, got dict
> *— task_007*

## References
- `agent/planner.py:88` — builds the args dict; no type coercion before dispatch.

## Suggested directions
- Validate arg types in the planner before dispatch.

## Rejected Store Memory (RSM)
(Empty at discovery; the solver appends dead-end attempts here so future rounds don't retry them.)
```

### RSM entry format (append-only, inside the weakness md)

```markdown
### Round N · `<rejected-direction-slug>`
- **Thesis**: <one line>
- **Change**: <files touched, summarized>
- **Metrics (weakness tasks)**: <primary> <value>[, <secondary> <value>, …]   # always record the attempt's measured metrics
- **Why rejected**: <dead end → no gain (≤ baseline) · or reverted → round regressed, rolled back>
- **Branch**: <the unmerged branch the attempt lives on>
```

Include the metric **value** the attempt reached in the `Result` line (e.g. `reward 0.48`): the
dashboard parses it and shows that number on the red timeline node, so a reader sees *how far it
dropped*, not just that it was rejected.

Read the full RSM before proposing a fix; treat "the same idea but stricter" as a re-propose and pick
a genuinely different angle.
