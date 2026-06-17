# GEPA concepts

Background and design notes for the `gepa` algorithm skill. Primary source: GEPA —
*Reflective Prompt Evolution Can Outperform Reinforcement Learning* (Agrawal et al.,
2025, **arXiv:2507.19457**), and the `dspy.GEPA` implementation. We adopt the
patterns, not the code.

## Contents

- [Why GEPA is sample-efficient](#why-gepa-is-sample-efficient)
- [The two-stage economy: minibatch local gate → full-val gate](#the-two-stage-economy)
- [Reflective dataset (actionable side information)](#reflective-dataset)
- [Per-instance Pareto frontier + frequency-weighted sampling](#per-instance-pareto-frontier)
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
distinguishes this skill from the thin `gepa-reflective` (which evaluates every
proposal on full val).

1. **Minibatch local gate (cheap).** Each iteration samples a small minibatch of
   train ids, evaluates the parent and the proposed child on *that same minibatch*
   (one trial each), and accepts the child into the expensive stage only if
   `sum(child) > sum(parent)` on the minibatch. A proposal that doesn't even help a
   handful of tasks is discarded for the price of `2·minibatch_size` rollouts.
2. **Full-val gate (honest, expensive).** Only on a local pass does the child get a
   full-val evaluation and the **paired significance gate** (`gate.decide`,
   val-only) — the identical gate hill-climb uses. This is where acceptance is
   *decided*; the minibatch never decides acceptance, only whether to pay.

The minibatch is drawn from **train**, full-val from **val**, and **test is never
touched** by the loop. That ordering is the honesty guarantee: the optimizer only
ever sees train (via the reflective dataset) and is judged on held-out val.

## Reflective dataset

For the parent's **failing minibatch tasks**, the loop writes `REFLECTION.md` into
the optimizer's workdir containing, per task: the task **input**, the agent's
**output / compacted trajectory**, and the scorer's **feedback**. This is GEPA's
"actionable side information." It is written as a *file* (not inlined into a giant
prompt) because agents read files far better than long prompts, and the prompt just
points at it. Tasks that failed with an infra/run error (`Rollout.error`, surfaced
as `raw.errored`) are listed separately and explicitly excluded from "fix this" —
they are environment noise no edit can repair.

## Per-instance Pareto frontier

Instead of always extending the single global best (hill-climb) the parent is
**sampled from the per-instance Pareto frontier** (`selection.pareto_per_instance`).
For each val task, the candidate(s) achieving the best reward on it are that task's
winners; a candidate's sampling weight is **how many tasks it wins**
(frequency-weighted). This keeps:

- **specialists** — a candidate that uniquely tops one hard task survives even when
  its *mean* is below the incumbent's;
- **stepping-stones** — a lower-mean candidate that opens a path to a higher peak.

It is the quality-diversity intuition behind MAP-Elites / AlphaEvolve, applied to
capability text. `selection.py` owns the picker so there is one implementation
feeding both the loop and the dashboard.

## Round-robin component focus

A candidate's **components** are its editable capability files (scratch/memory files
and vcs dirs excluded — the same exclusion the eval cache uses). With
`--component-selector round_robin` the loop focuses **one component per iteration**
(cycled), writing the choice to `FOCUS.md`, so each proposal is a small, attributable
change — which is exactly the unit the system-aware merge later recombines. `all`
lists every component for cross-cutting edits or monolithic capabilities.

## System-aware merge

GEPA's **system-aware merge** is crossover across two complementary lineages. After
an accept (gated by `--merge-cadence` and bounded by `--max-merges`) the loop looks
for two frontier dominators that share a **common ancestor both improved on**, and
builds a merged candidate **component-by-component**: start from the ancestor, then
for each component take whichever descendant *changed* it (deterministic tie to the
better-val side). The merge is then **minibatch-gated** (`>= max(parents)` on the
minibatch) before the standard full-val gate, so a bad recombination costs little.

For a **monolithic single-component** capability there is nothing independent to
recombine, so the merge **skips gracefully** (logged `gepa_merge_skip`) rather than
emitting a degenerate child. (Decomposing a monolith by markdown section is a
possible future refinement.)

## Budget, cache, honesty

- **Budget is in metric-calls** (`--max-metric-calls`, primary) — every rollout, on
  the minibatch *and* on full val, is counted via `run_dir.update_spent(metric_calls=
  …)`. `--max-iterations` is a secondary cap. This makes the rollout economy the
  thing the budget actually constrains, matching the paper's accounting.
- **Eval cache** keys `(hash(candidate editable files), task_id) → reward/feedback`,
  so a re-sampled parent or a byte-identical candidate pays nothing for a rollout it
  already ran. Cache hits do **not** count toward the metric-call budget (they fired
  no rollout); the event log still records every evaluation.
- **Honesty is the engine's, untouched.** Acceptance is gated on val only; the gate,
  the paired significance test, the SE-collapse warning, and the test seal are all
  the same core code the rest of the family uses. The loop adds control flow, not new
  scoring or gating.

## Relation to the family

- **`gepa-reflective`** is the thin precursor: per-task Pareto selection + a
  reflective dataset over failing *val* tasks, but **no minibatch economy and no
  merge** — every proposal is evaluated on full val. This `gepa` skill supersedes it
  for real runs; `gepa-reflective` remains as the minimal illustration of the two
  core ideas and as a `harness.pareto_loop` smoke. Prefer `gepa` when rollouts are
  expensive.
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
