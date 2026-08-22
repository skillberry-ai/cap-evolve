# GEPA concepts

Background and design notes for the `gepa` algorithm skill. Primary source: GEPA —
*Reflective Prompt Evolution Can Outperform Reinforcement Learning* (Agrawal et al.,
2025, **arXiv:2507.19457**), and the `dspy.GEPA` implementation. We adopt the
patterns, not the code.

## Contents

- [Why GEPA is sample-efficient](#why-gepa-is-sample-efficient)
- [The two-stage economy: minibatch local gate → full-val gate](#the-two-stage-economy)
- [Reflective dataset: source, limits, and what the writer omits](#reflective-dataset)
- [Per-instance winners vs. the strict Pareto frontier](#per-instance-pareto-frontier)
- [Round-robin component focus](#round-robin-component-focus)
- [System-aware merge](#system-aware-merge)
- [Budget in metric-calls, the eval cache, and honesty](#budget-cache-honesty)
- [Relation to the other family members](#relation-to-the-family)
- [Sources](#sources)

## Why GEPA is sample-efficient

GEPA's thesis: **natural language is a richer learning medium than a scalar
reward.** An English diagnosis of *why* a rollout failed — read off the actual
trajectory and the scorer's feedback — is the textual analogue of a gradient.
Reflecting on traces lets each proposal carry far more information than a reward
number, so GEPA reports matching or beating RL (GRPO) with **up to ~35× fewer
rollouts**, and +10% over MIPROv2. The whole design is organized around spending
expensive evaluations only when a cheap signal says it is worth it.

## The two-stage economy

The economy is the part that makes the "sample-efficient" claim real, and is what
makes it sample-efficient: most proposals are filtered cheaply on a minibatch
before any full-val evaluation is paid for.

1. **Minibatch local gate (cheap).** Each iteration samples a small minibatch of
   train ids, evaluates the parent and the proposed child on *that same minibatch*
   (one trial each), and accepts the child into the expensive stage only if
   `sum(child) > sum(parent)` on the minibatch. A proposal that doesn't even help a
   handful of tasks is discarded for the price of `2·minibatch_size` rollouts.
2. **Full-val gate (honest, expensive).** Only on a local pass does the child get a
   full-val evaluation and the **paired significance gate** (`gate.decide`,
   val-only) — the identical gate hill-climb uses. This is where acceptance is
   *decided*; the minibatch never decides acceptance, only whether to pay.

The minibatch is drawn from **train** and full-val from **val**. That ordering is
what keeps the proposer away from the split its own gate is computed on. Caveat:
if `splits.train` is empty the loop falls back to val ids (`gepa.py:518`) with no
warning, which breaks exactly that separation — do not run with a zero train split.

## Reflective dataset

For the parent's **failing minibatch tasks** (`reward < 1.0`), the loop writes
`REFLECTION.md` into the optimizer's workdir. `phases/diagnose` owns what a
reflective dataset is and what shape it takes; what matters here is the source and
the limits. It is written as a *file* rather than inlined into a giant prompt
because agents read files far better than long prompts, and the prompt just points
at it. Tasks that failed with an infra/run error (`Rollout.error`, surfaced as
`raw.errored`) are listed separately and explicitly excluded from "fix this" — they
are environment noise no edit can repair.

What the shipped writer actually emits, per task, is the agent's output, its
compacted trajectory, and the scorer's feedback — each truncated (~1500 chars at
capture, ~800 in the file), for at most 12 failing tasks. The task **input** is
not written, although `gepa.py`'s own docstring claims it is; and on an eval-cache
hit the cached record holds only `{reward, feedback}`, so the output line comes out
empty (#111). Both are core bugs, not intended design: GEPA §3's "actionable side
information" is the (input, output, feedback) triple, and dropping the input leaves
the optimizer diagnosing a bad answer to an unknown question.

## Per-instance Pareto frontier

Instead of always extending the single global best (hill-climb) the parent is
**sampled over per-instance winners** (`selection.pareto_per_instance`). For each
val task, the candidate(s) achieving the best reward on it are that task's winners;
a candidate's sampling weight is **how many tasks it (co-)wins**
(frequency-weighted), and a candidate that wins nothing is never sampled.

The sampling pool is *not* the strict Pareto frontier: `_pick_pareto_per_instance`
never calls `pareto_frontier`, so a candidate that merely ties for a win stays in
the pool even when another candidate dominates it on every task. The strict
frontier (`selection.pareto_frontier`) is a subset, and is what the system-aware
merge searches and what the run's reported `frontier_size` counts. Keeping the
looser pool is defensible — a tie-winner is still evidence that one task is
solvable from that text — but it is a different set, so do not read "frontier" as
one thing.

Either way this keeps:

- **specialists** — a candidate that uniquely tops one hard task survives even when
  its *mean* is below the incumbent's;
- **stepping-stones** — a lower-mean candidate that opens a path to a higher peak.

It is the quality-diversity intuition behind MAP-Elites / AlphaEvolve, applied to
capability text. `selection.py` owns the picker so there is one implementation
feeding both the loop and the dashboard.

## Round-robin component focus

A candidate's **components** are its editable capability files (`NON_CAPABILITY_FILES`
scratch/memory files and `NON_CAPABILITY_DIRS` vcs/read-context dirs excluded — the same
exclusion the eval cache uses). That list covers the whole injected read-context — the
optimizer-agent dotfiles (`.claude/`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) as well as
`guidance/`, `trajectories/` and `prior_iterations/` — so round-robin cannot spend an
iteration focused on one of them, and an un-ignored read-context dir cannot bust the eval
cache every iteration. With
`--component-selector round_robin` the loop focuses **one component per iteration**
(cycled), writing the choice to `FOCUS.md`, so each proposal is a small, attributable
change — which is exactly the unit the system-aware merge later recombines. `all`
lists every component for cross-cutting edits or monolithic capabilities.

## System-aware merge

GEPA's **system-aware merge** is crossover across two complementary lineages. After
an accept (gated by `--merge-cadence` and bounded by `--max-merges` **attempts** —
a merge rejected at either gate consumes one; a skip for want of an eligible pair is
free) the loop looks for two strict-frontier dominators that share a **common
ancestor both improved on**, and builds a merged candidate **component-by-component**:
start from the ancestor, then for each component take whichever descendant *changed*
it. If both changed it the tie goes to `a`, which is simply the first of the pair in
frontier iteration order — `_build_merge` never sees a val score. (Val order only
decides which parent the *gate* compares against.) The merge is then
**minibatch-gated** (`>= max(parents)` on the minibatch) before the standard
full-val gate, so a bad recombination costs little.

For a **monolithic single-component** capability there is nothing independent to
recombine, so the merge **skips gracefully** (logged `gepa_merge_skip`) rather than
emitting a degenerate child. (Decomposing a monolith by markdown section is a
possible future refinement.)

## Budget, cache, honesty

- **Budget is in metric-calls** (`--max-metric-calls`, primary) — every rollout, on
  the minibatch *and* on full val, is counted via `run_dir.update_spent(metric_calls=
  …)`. `--max-iterations` is a secondary cap. This makes the rollout economy the
  thing the budget actually constrains, matching the paper's accounting. It is a
  **stop, not a cap**: `_budget_left()` runs once per iteration, at the top, so an
  iteration that starts one rollout under budget still spends its two (or three)
  minibatches plus a full-val eval. Budget your ceiling with that slack.
- **Eval cache** keys `(hash(candidate editable files), task_id) → reward/feedback`,
  so a re-sampled parent or a byte-identical candidate pays nothing for a **minibatch**
  rollout it already ran. The full-val path (`harness.evaluate_candidate`) never
  consults the cache and charges unconditionally. Cache hits do not count toward the
  metric-call budget (they fired no rollout); the event log still records every
  evaluation. The cache is also why reflection can come out hollow — see above.
- **The loop adds control flow, not scoring or gating.** Acceptance, the paired
  significance test, the SE-collapse warning and the seal are all the same core code
  the rest of the family uses.

## Relation to the family

- **`hill-climb`** always extends the single global best with a focus *schedule*; no
  frontier, no minibatch gate. Best for the first baseline run and for
  feedback-poor binary tasks where reflection has little to work with.
- **`skillopt`** is a strict single-lineage climb with a textual learning-rate
  (edit-budget schedule) and an epoch-boundary slow update; choose it when a fixed
  schedule and longitudinal review fit better than GEPA's frontier exploration.

## Sources

- Agrawal et al., 2025. *GEPA: Reflective Prompt Evolution Can Outperform
  Reinforcement Learning.* **arXiv:2507.19457**.
- `dspy.GEPA` (DSPy) — reference implementation of reflective evolution + Pareto
  candidate selection.
- MAP-Elites / AlphaEvolve / OpenEvolve — the quality-diversity lineage behind
  keeping a frontier of complementary specialists rather than a single champion.
