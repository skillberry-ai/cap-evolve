# SkillOpt — concepts

Load this when you need to change `skillopt_loop` or reason about its rollout
cost. To *run* the algorithm, `SKILL.md` is enough.

SkillOpt (arXiv:2605.23904, *Executive Strategy for Self-Evolving Agent Skills*)
is a single-lineage capability optimizer: like `hill-climb` the parent is always
the current best, but the run is organized into epochs over mini-batches with a
decaying integer edit budget and one extra consolidation step per epoch. It edits
whatever the selected capability owns; nothing in the loop assumes a skill
package, despite the name.

## The loop

`cap_evolve.skillopt.skillopt_loop(adapter, *, run_dir, optimizer, current_val, …)`:

1. Init memory + version store (`harness._init_memory_store`). Compute
   `steps_per_epoch = ceil(len(train) / (batch_size · accumulation))`,
   `total_steps = epochs · steps_per_epoch`, and the integer edit-budget schedule
   `build_schedule(lr_schedule, max=edit_budget, min=min_edit_budget, total=total_steps)`
   (default `cosine`, 4 → 2).
2. **Each epoch**: shuffle the train ids (`random.Random(1000 + epoch)`, so a
   rerun reproduces), reset the per-epoch `step_buffer` and `rejected_this_epoch`,
   and record the epoch-start candidate id.
3. **Each step**: take the accumulation window of the shuffled order as the
   mini-batch and build the instruction string —
   `harness._focus_instructions(current_val, focus_ids=minibatch_ids, label)` plus
   the SkillOpt block (`L`, the rejected ids to avoid this epoch, the unsolved
   failure patterns). **Both the focus filter and the failure-pattern filter are
   currently empty by construction — see the gap below.** Parent is always the
   current best. `harness.run_step(...)` does the rest: materialize, optimize,
   evaluate on val, apply the gate, snapshot + set best on accept, write
   RejectedMemory/History.
4. Append a bounded record to `step_buffer`
   (`{step, epoch, accepted, n_fail, failure_patterns, rejected id + val Δ}`),
   capped at ≤3 task ids per pattern, ≤10 patterns, ≤12 steps
   (`_MAX_*` in `skillopt.py:58-60`), and reset each epoch so the prompt cannot
   balloon. Note `_MAX_BUFFER_STEPS` — a *step* cap — is reused to slice the
   *reject* list at `skillopt.py:122`.
5. Update `current_val` only on accept.
6. **End of epoch** (from epoch 2, unless `--no-slow-update`): the gated
   consolidation step below.
7. Return a result dict shaped like `hill_climb_loop`'s, plus `epochs`,
   `edit_budget_schedule`, `epoch_stats` and `slow_updates`.

### Gap: the mini-batch is not actually in focus (issue #371)

`minibatch_ids` come from `run_dir.read_splits().train` (`skillopt.py:230`) but
are used to filter the parent's **val** per-task rows (`skillopt.py:291`,
`:315`, `:319` → `harness.py:2011-2012`). `make_splits` assigns train/val/test as
disjoint slices of one shuffled list (`splits.py:117-119`), so every filter
yields nothing. Observed on `SyntheticAdapter(n=12)`:

```
train: ['t1','t9','t8','t5','t10','t2']   val: ['t3','t7','t4']   train ∩ val: set()
Focus: epoch 1/1 step 1/3 (mini-batch of 2 train tasks, L=4).
Current val reward 0.000: 0 solid / 0 flaky / 0 failing of 0 tasks.
'## Failure patterns still unsolved' ever rendered? False
```

So `n_fail` is always 0 and step 4's `failure_patterns` is always `[]`. Fixing
this means either evaluating the mini-batch on **train** and reflecting on that
result (gepa's `_eval_minibatch` exists for exactly this) or deriving the focus
ids from val. The two readings imply different rollout costs; #371 is the
decision.

## Textual learning rate (edit budget)

`core/cap_evolve/lr_schedule.py`. Integers only — you cannot make 2.7 edits —
clamped to `[min_lr, max_lr]`, `total_steps <= 0` yields `[]`, and `constant` or
`total_steps == 1` sits at `max_lr` (`lr_schedule.py:42-55`). Worked values,
`max=4 min=2 total=12`:

```
constant  [4,4,4,4,4,4,4,4,4,4,4,4]
linear    [4,4,4,3,3,3,3,3,3,2,2,2]
cosine    [4,4,4,4,3,3,3,3,2,2,2,2]
```

`linear` and `cosine` differ at 2 of 12 positions. Over a 3-value integer range
the schedule choice is close to a no-op; `SKILL.md` § "The textual learning rate"
argues why the decay is a heuristic rather than a demonstrated mechanism.

`L` reaches the optimizer as prose only; nothing clips the edit count. The
`requested_edits` / `applied_changes` pair logged at `skillopt.py:338` is not a
guardrail: `_changed_components` (`:398-427`) counts files whose bytes differ,
and `applied_changes` is read by nothing in `core/`, `dashboard/` or `skills/`.

## The within-epoch buffer

Two per-epoch bounded structures appended to the next step's prompt:

- **rejected-edit list** — each rejected candidate's id and val Δ
  (`skillopt.py:120-125`). It does not carry the *content* of the rejected edit,
  so an optimizer cannot avoid an approach it was never shown. The `LEDGER.md`
  that `run_step` injects into every workdir already lists each prior edit's
  outcome and the tasks it broke and fixed, run-global rather than per-epoch —
  strictly stronger. Treat this list as redundant.
- **failure-pattern block** — failing feedback clustered by a normalized 8-word
  prefix, infra-errored tasks dropped via `raw.errored` (`skillopt.py:65-93`).
  Sound logic, currently fed an empty list (see the gap above).

## The epoch-boundary consolidation step

From epoch 2, compare the epoch-start candidate against the current best and
bucket each task:

- **regressed** — passed at epoch start, now failing;
- **persistent_fail** — failing both times;
- **stable_success** — passing both times;
- **improved** — reward rose. Computed with a bare `if` before the exclusive
  chain (`skillopt.py:184-191`), so a 0.2 → 0.5 task lands in both `improved` and
  `persistent_fail`; `_slow_update_instructions` (`:139-166`) renders only the
  first three. Read `improved` as an overlapping counter, not a partition member.

The longitudinal instruction ("fix the REGRESSIONS and chip at the PERSISTENT
failures without breaking any STABLE SUCCESS") goes through one ordinary
`harness.run_step` (`skillopt.py:479-485`) — same val gate, never force-accepted.
`skills/algorithms/skillopt/scripts/check.py:108-112` asserts the step carries a
gate decision, which is the regression guard on that property.

### Gap: the cost and the comparison

- The re-evaluation calls `harness.evaluate_candidate(..., split="train")` twice
  with **no** `ids=` (`skillopt.py:458-463`) and only then filters to the ~20
  sampled ids (`:464-466`). Budget `2 · len(train) · n_trials` rollouts per
  epoch boundary, not `2 · sample · n_trials`.
- The re-eval is guarded by `prev_epoch_best_id != run_dir.best_id`
  (`skillopt.py:455`). If the epoch accepted nothing, both sides remain
  `current_val` — the identical list — so the buckets are computed over **val**
  tasks and report 0 regressed / 0 improved, while the logged `sample=` is a
  train count that was never scored (`:469-470`). The consolidation step runs
  anyway, on an instruction describing no actual change.
- `skillopt.py:147` writes "the skill" into that prompt for every capability
  type. An algorithm must not name a capability it cannot know.

## Where it lives

- Loop: `core/cap_evolve/skillopt.py` (`skillopt_loop`).
- Schedule: `core/cap_evolve/lr_schedule.py` (`build_schedule`).
- The shared step: `core/cap_evolve/harness.py` (`run_step`,
  `evaluate_candidate`, `_focus_instructions`, `_init_memory_store`) — its
  contract is documented by `algorithms/hill-climb`.
