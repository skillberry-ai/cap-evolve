# SkillOpt — concepts

SkillOpt (arXiv:2605.23904) is a single-lineage capability optimizer that adapts
the deep-learning training loop to *textual* skill editing. It sits between
`hill-climb` (one-shot, whole train set) and `gepa` (a per-instance Pareto
frontier): like hill-climb the parent is always the current best, but the run is
organized into **epochs × mini-batches** with a **decaying edit budget** and a
per-epoch **slow/meta update** — the disciplined annealing hill-climb lacks
without gepa's frontier bookkeeping.

## Contents
- [The loop](#the-loop)
- [Textual learning rate (edit budget)](#textual-learning-rate-edit-budget)
- [The within-epoch buffer](#the-within-epoch-buffer)
- [The epoch-boundary slow / meta update](#the-epoch-boundary-slow--meta-update)
- [Honesty + pitfalls](#honesty--pitfalls)
- [Where it lives](#where-it-lives)

## The loop

`cap_evolve.skillopt.skillopt_loop(adapter, *, run_dir, optimizer, current_val, …)`:

1. Initialize memory + version store (`harness._init_memory_store`). Compute
   `steps_per_epoch = ceil(len(train) / (batch_size·accumulation))`,
   `total_steps = epochs · steps_per_epoch`, and the integer edit-budget schedule
   `build_schedule(lr_schedule, max=edit_budget, min=min_edit_budget, total=total_steps)`
   (default `cosine`, 4 → 2).
2. **Each epoch**: shuffle the train ids (seeded by epoch), reset the per-epoch
   `step_buffer` and `rejected_this_epoch`, and snapshot the epoch-start skill as
   `prev_epoch_skill`.
3. **Each step**: take the accumulation window of the shuffled order as the
   mini-batch; build focus instructions over ONLY those tasks
   (`harness._focus_instructions(current_val, focus_ids=minibatch_ids, …)`) and
   append the SkillOpt buffer block (the edit budget `L`, the rejected edits to
   avoid this epoch, the unsolved failure patterns). Parent is **always the
   current best** (single lineage). Call `harness.run_step(...)` — it materializes
   the parent, runs the optimizer, evaluates on VAL, applies the significance
   gate, snapshots + sets best on accept, and writes RejectedMemory/History.
4. Append a bounded record to `step_buffer`
   (`{step, epoch, accepted, n_fail, failure_patterns, rejected id + val Δ}`),
   capped (≤ 3 task ids per pattern, ≤ ~10 patterns, ≤ 12 steps) and **reset each
   epoch** so the prompt cannot balloon.
5. Update `current_val` only on accept (equivalent to reading back `run_dir.best`,
   as hill-climb does).
6. **End of epoch** (from epoch 2, if slow-update on): the gated slow/meta update
   (below).
7. Return a result dict (best id, val reward, accept/reject counts, the schedule,
   per-epoch stats, slow-update records) — shaped like `hill_climb_loop`'s.

## Textual learning rate (edit budget)

The "learning rate" is how many edits the optimizer may make in one step: a large
budget early to explore broadly, shrinking later to consolidate. We reuse the
familiar `constant | linear | cosine` LR shapes from `core/lr_schedule.py` but
emit **integers** (you cannot make 2.7 edits). `L` is passed to the optimizer in
**natural language** ("make at most L bounded add/delete/replace edits") — the LLM
is *not* mechanically clipped — so the loop logs **requested-vs-applied** (a
best-effort file-diff count) to surface an optimizer that ignores its budget.

## The within-epoch buffer

Two per-epoch, bounded structures injected into the next step's prompt:

- **rejected-edit buffer** — every rejected candidate's id + val Δ, so the
  optimizer does not re-propose a dead end *this epoch* (the global RejectedMemory
  in `run_step` still records all rejects across the run).
- **failure-pattern block** — the focus tasks' failing feedback clustered by a
  normalized prefix signature (infra-errored tasks excluded via the structured
  `raw.errored` flag), so the prompt carries *patterns* not raw prose.

Both reset at the epoch boundary; both are length-capped (`_MAX_*` constants) so
the optimizer prompt stays small as the run grows.

## The epoch-boundary slow / meta update

Paper §3.6's **gated** mode. At the end of each epoch (from epoch 2), re-evaluate
the epoch-start skill snapshot vs the current best on a **small sampled TRAIN
subset** (default ~20 ids), categorize each task:

- **improved** — reward rose;
- **regressed** — passed at epoch start, now failing;
- **persistent_fail** — failing both epochs;
- **stable_success** — passing both epochs.

Build a longitudinal instruction ("fix the REGRESSIONS and chip at the PERSISTENT
failures without breaking any STABLE SUCCESS") and run ONE extra `run_step` —
**gated on val exactly like a normal step**. It is *never* force-accepted and
*never* bypasses the val gate to mutate best. The sample is small, toggleable
(`--no-slow-update`), and counted in budget.

## Honesty + pitfalls

- **Gate on val, test sealed.** Acceptance always routes through `gate.decide` on
  the VAL split; the test seal is only touched by `finalize`.
- **Default to `significant`/`paired`, not strict.** A tiny val set with a naive
  strict-greater gate rejects almost everything on noise. With a small val set,
  raise `--n-trials` for real per-trial variance, or use a **graded** reward so
  the paired significance test has signal.
- **Only the slow update is "meta", and it is still gated** — never a force-accept.
- **Reset + bound the buffer per epoch** so the optimizer prompt does not balloon.
- **`L` is natural-language only** (no mechanical clip); log requested-vs-applied.

## Where it lives

- Loop: `core/cap_evolve/skillopt.py` (`skillopt_loop`).
- Schedule: `core/cap_evolve/lr_schedule.py` (`build_schedule`).
- The honesty-critical step: `core/cap_evolve/harness.py` (`run_step`,
  `evaluate_candidate`, `_focus_instructions`, `_init_memory_store`).

Citation: SkillOpt, arXiv:2605.23904.
