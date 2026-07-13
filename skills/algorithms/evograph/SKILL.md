---
name: evograph
description: >-
  evo-graph as a cap-evolve algorithm (AGENT MODE ONLY): a collaborative weakness-graph optimizer.
  Each round re-evaluates the train split, clusters failures into a shared Obsidian-style markdown
  "weakness graph", dispatches one solver agent per weakness in its own git worktree scoped to that
  weakness's frozen affected_tasks, merges verified improvements, reverts a whole round on regression,
  and repeats until the spec's stop_condition — then seals the test once via `cap-evolve finalize`.
  Writes a wiki into the run dir + a custom_view.json so its weakness-graph tab shows in the dashboard.
  USE when algorithm_skill: evograph and orchestration_mode: agent.
component: algorithm
argument-hint: "(agent mode) driven by the coding agent per orchestration_mode: agent"
allowed-tools: Read, Write, Edit, Bash
needs: [scores, traces, candidate]
provides: [candidate]
sources: [evo-graph]
---

# evograph — collaborative weakness-graph optimizer (agent mode)

evograph is **agent-mode only** (`orchestration_mode: agent`). There is no deterministic engine — a
weakness-graph loop is agent-driven by nature. When a run selects `algorithm_skill: evograph`,
cap-evolve runs intake → check → baseline and then hands **you, the coding agent in the conversation,**
the loop (per the orchestrate skill's *Agent-mode loop*). You drive it yourself; you do not delegate
the search to a separate optimizer agent, though you DO dispatch solver subagents for parallel work.

## How this differs from stock evo-graph (it fits cap-evolve)

evograph keeps evo-graph's *distinctive* machinery — the weakness graph, per-weakness solver
worktrees, whole-round revert, and the wiki file formats the dashboard reads — but everything else is
cap-evolve's:

| stock evo-graph | evograph in cap-evolve |
|---|---|
| its own setup Q&A (`questions.md`) | **cap-evolve `intake`** — read the spec (`capevolve.yaml`); ask nothing of your own |
| "discover & run the bench yourself" | **cap-evolve adapter + harness** — evaluate through `cap-evolve` (writes run-dir rollouts/results) |
| its own train/test split | **cap-evolve seeded splits** (`splits.json`); train each round, **test sealed** |
| its own final-test.json + cost prompt | **`cap-evolve finalize`** produces the sealed number; mirror it into the wiki for the view |
| wiki under `.evograph/` | wiki under the **cap-evolve run dir** (`<run_dir>/wiki/…`) so the dashboard tab reads it |
| primary/secondary from its own config | the spec's `metric_primary` / `metrics_display` (**#38**) — gate on the primary only |

Do **not** re-ask setup questions, invent a split, or run a raw bench command. Read the spec and use
cap-evolve's primitives. This is what keeps the run honest (sealed test, val/train-gated) and the
default dashboard tabs populated.

## Vocabulary (canon — used in the wiki and the dashboard)

Unchanged from evo-graph — the dashboard tab depends on these exact terms/formats:

- **Weakness** — a recurring failure pattern hurting the primary metric (incl. inconsistency). One
  node per weakness: `<run_dir>/wiki/weaknesses/<slug>.md`.
- **Solution** — one kept improvement, under `<run_dir>/wiki/solutions/<slug>/<sol-id>/`.
- **Status** — `open | in-progress | completed | solved | reverted`.
- **RSM (Rejected Store Memory)** — the dead-end log inside each weakness md; read before proposing.

## Hard rules (honesty — never violate)

1. **The sealed test split is untouchable until the end.** Evaluate only on train (rounds) / the
   affected_tasks; never score test until the final `cap-evolve finalize` (which owns the seal —
   `RunDir.reserve_test`/`commit_test`). One test scoring, ever.
2. **Acceptance is gated on the primary metric.** A merge/solution is kept only if it improves the
   primary metric over its baseline on the relevant tasks; a whole round reverts if the round-start
   train primary metric regressed. Secondary metrics (`metrics_display`) are shown, never gate.
3. **Drive through cap-evolve primitives.** Every eval goes through the cap-evolve adapter/harness so
   per-rollout JSON + results land in the run dir; log round boundaries via the run dir event log;
   snapshot accepted candidates via the store. This keeps the default dashboard tabs live in addition
   to evograph's own tab.
4. **Isolate edits in git worktrees.** The capability under optimization is edited only inside
   per-weakness worktrees on their own branches — never the user's checkout. (Same discipline as
   evo-graph's Step 0; here the "capability" is cap-evolve's `capability_path` artifact.)

## Step 1 — Read the spec + launch the view (no eval yet)

- Read `capevolve.yaml`: `metric_primary` + `metrics_display` (#38), `stop_condition`,
  `github_integration`, `capabilities`/`capability_path`, splits. cap-evolve intake already collected
  these — do not re-ask.
- Scaffold the wiki under the run dir and start evograph's dashboard, then declare it to the
  cap-evolve dashboard so its tab appears (the #39 custom-view contract):
  - create `<run_dir>/wiki/{weaknesses,solutions,results}` and `<run_dir>/runs/`.
  - launch the bundled weakness-graph view and register it in one step:
    `python skills/algorithms/evograph/scripts/view.py --run-dir <abs run_dir> --port <port> &`.
    It writes `<run_dir>/custom_view.json` (`{"title":"Weakness graph","url":"http://127.0.0.1:<port>/"}`)
    so the cap-evolve dashboard mounts a **Weakness graph** tab embedding it, and serves evo-graph's
    read-only React UI (this skill's `dashboard/`) pointed at the run dir. Give the user both links.
    (Deps once: `pip install -r skills/algorithms/evograph/dashboard/backend/requirements.txt`.)

## Step 2 — Round loop (you drive it, uninterrupted to stop_condition)

Re-read `stop_condition` at the end of every round (free text; no built-in default).

### 2.1 Eval all train tasks (via cap-evolve)
Evaluate the current candidate on **all train tasks** through cap-evolve's eval (round 1 = the
baseline you were handed). Tag the candidate's git state so a later round can roll back. Write
`<run_dir>/wiki/results/round-<N>.json` (format: [references/dashboard.md](references/dashboard.md)),
stamping `started_at` from `scripts/now.py`. Stamp all-perfect weaknesses `solved`.

### 2.2 Regression check + whole-round revert (round ≥ 2)
Compare this round's **primary metric** to `round-<N-1>.json`. If it dropped, round N−1's merges
regressed the suite → reset the candidate to the pre-round-(N−1) tag, re-eval, overwrite the results,
mark those weaknesses `reverted` (eligible again), demote their solutions into RSM.
[references/graph.md](references/graph.md).

### 2.3 Build / extend the weakness graph
Dispatch builder subagents to read the round's **failed** (and contrasting **successful**)
trajectories and write `<run_dir>/wiki/weaknesses/<slug>.md` directly — match+extend or create.
Aim for **breadth (≥ 4 distinct weaknesses)** when the failures support it. `affected_tasks` is
**frozen** at discovery. Do a light dedup pass. Schema + freeze rule:
[references/clustering.md](references/clustering.md).

### 2.4 Solve — one solver per weakness
For each `open | completed | reverted` weakness, mark it `in-progress` and dispatch one solver in its
own worktree (weakness branch → solution branch; names in [references/graph.md](references/graph.md)).
Each solver: baseline the primary metric on its frozen `affected_tasks` (reuse round-start scores) →
edit the capability → re-eval **only affected_tasks** via cap-evolve → keep if improved, else revert
and try another angle → aim for ~2–3 improving iterations. Append progress to
`<run_dir>/runs/round-<N>/agents/<slug>.log` (streamed live in the tab). Ship a real improvement →
write `wiki/solutions/<slug>/<sol-id>/{solution.md,changes.diff}` with real before/after numbers,
request merge, set `completed`/`solved`. Dead end → RSM, no merge.

### 2.5 Merge (you)
Trust the solver's reported result and merge into the working candidate; the round-start eval (2.1→2.2)
is the objective backstop. If `github_integration: true`, mirror the weakness as a GitHub issue and
ship the merge as a PR (`Closes #n`) — GitHub is **mirror-only**, the run dir stays authoritative
(this is evograph's realization of #38's `github_integration`).

### 2.6 Stop check + dashboard verify
Stamp `completed_at`, log the round to the run dir event log, snapshot the accepted candidate via the
store. **Verify the run dir has what both dashboards need** (round results written, weakness nodes +
solution cards + logs present, standard events/rollouts emitted). Re-read `stop_condition`; continue
(2.1) or halt.

## Step 3 — Final test (once, after halt)
Call `cap-evolve finalize` — it scores the best candidate on the sealed test split exactly once and
burns the seal (unfakeable headline number). Mirror that number into `<run_dir>/wiki/results/final-test.json`
(`"split":"test"`, `"round":"final"`) so evograph's tab shows it in its Final-test panel. Then
`cap-evolve report`.

## Cost — use cap-evolve's cost system (not a separate one)
Do **not** run a bespoke end-of-run cost prompt. Cost is cap-evolve's job: every eval you drive
through cap-evolve records spend in the run dir (`RunDir.update_spent`), the default dashboard **Cost**
tab renders it, and the spec's `max_usd` / `max_optimizer_usd` caps bound it (preview with
`cap-evolve estimate`). If you want the evograph tab's Final-test panel to show a cost number, read it
from cap-evolve's recorded run-dir spend and mirror it into `final-test.json` as `cost_usd` — never ask
the user to hand-total it.

## References
- [references/clustering.md](references/clustering.md) — weakness schema, direct-write build, freeze rule.
- [references/graph.md](references/graph.md) — branch/PR model, solution layout, `related` edges.
- [references/dashboard.md](references/dashboard.md) — the wiki file formats the tab reads (the contract).
