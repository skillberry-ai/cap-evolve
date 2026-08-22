---
name: skillopt
description: Runs the SkillOpt single-lineage optimization loop, which organizes a hill-climb into epochs over mini-batches of train tasks under a textual learning rate — an integer edit budget that decays on a constant|linear|cosine schedule — and ends each epoch with one extra gated consolidation step. Parent is always the current best; acceptance is the val significance gate. Use when a run should anneal from broad early edits to small late ones and consolidate once per epoch, rather than hill-climb's one-shot whole-trainset proposals or gepa's Pareto frontier.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer CMD [--epochs 4] [--batch-size N] [--accumulation 1] [--edit-budget 4] [--min-edit-budget 2] [--lr-schedule cosine] [--no-slow-update]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
---

# skillopt — annealed single-lineage climb (epochs × mini-batches)

SkillOpt (arXiv:2605.23904, *Executive Strategy for Self-Evolving Agent Skills*)
organizes a hill-climb into **epochs × mini-batches** under a decaying integer
**edit budget**. The name is the paper's; the algorithm edits whatever the
selected capability owns — a prompt, a tool surface, a skill package — and never
assumes which.

**Read the shared step first**, then this file. Parent materialization, the
optimizer call, the val evaluation, the significance gate, accept/reject,
snapshot/best, the memory and handover files: all of that is
`harness.run_step`, documented once in `algorithms/hill-climb/SKILL.md`
§ "One iteration, end to end" and `algorithms/hill-climb/references/run-step.md`
(both land with PR #370; until then read `harness.run_step` itself). This file
states only what SkillOpt does differently.

Know the bound before reaching for this algorithm: **`run_step` lets a caller
vary exactly two things — `parent_dir` and `instructions`.** SkillOpt pins
`parent_dir` to the current best, identical to hill-climb, so everything novel
lives in the `instructions` string plus the choice to run one extra step per
epoch. It is prompt shaping and step scheduling, not a different search.

## What SkillOpt does differently

1. **A decaying integer edit budget `L`.** `lr_schedule.build_schedule` emits one
   integer per step over `constant | linear | cosine`, clamped to
   `[--min-edit-budget, --edit-budget]` (`core/cap_evolve/lr_schedule.py:42-55`).
   `L` is stated to the optimizer in prose — "at most L bounded edits" — and is
   never mechanically enforced. See the next section before you tune it.
2. **A per-epoch rejected-edit list.** Each reject appends its candidate id and
   val Δ, and the next step's prompt asks the optimizer to avoid them
   (`skillopt.py:120-125`, `:322-327`). It carries no description of *what* the
   rejected edit changed, so treat it as a weak signal — the run-global
   `LEDGER.md` that `run_step` already injects names the tasks each prior edit
   broke and fixed, which is strictly more useful.
3. **One extra gated step per epoch boundary** (from epoch 2). It compares the
   epoch-start candidate against the current best, buckets tasks as
   regressed / persistent-failure / stable-success, and asks for a consolidating
   edit that fixes regressions without breaking the stable passes. It goes
   through the same `run_step` and the same val gate — it is never
   force-accepted (`skillopt.py:479-485`). Disable with `--no-slow-update`.
   A fourth bucket, `improved`, is computed and logged but is *not* exclusive
   with the others and never reaches the prompt (`skillopt.py:184-191`, `:139-166`).

Epochs shuffle the train ids seeded by epoch number, so a rerun is reproducible.
`steps_per_epoch = ceil(len(train) / (batch_size × accumulation))`.

## The textual learning rate, stated without the analogy

The knob is real: `L` decays, it is an integer, and the schedules are correct.
The *justification* is weaker than the ML vocabulary implies, and pretending
otherwise would mislead anyone tuning it.

What plausibly holds: the gate accepts or rejects a whole candidate. A candidate
bundling six edits where five help and one hurts is rejected entirely, and you
learn nothing about which edit was the problem. Fewer edits per candidate means
an accepted candidate is more likely to contain only good edits and a rejected
one is cheaper to attribute and revert. That argues for small edits — it does not
by itself argue for *decay*.

What does not transfer: in SGD, LR decay exists because nothing stops a large
step from overshooting near an optimum. Here the val significance gate already
rejects an overshooting edit before it can become the parent. The overshoot
protection is the gate, so the decay is not doing that job.

What is unmeasured: no ablation in this repo isolates the schedule's effect.
At realistic step counts the choice barely exists — over 12 steps from 4 down
to 2, `linear` and `cosine` differ at 2 of 12 positions. Prefer `constant` or
`linear` and spend your tuning budget on `--n-trials` and the gate instead. This
is a heuristic that has not been isolated; do not present it as a proven one.

## Known gaps

These are shipped-behavior defects in `core/cap_evolve/skillopt.py`. The skill
describes what the code does today, not what it intends to do.

- **The mini-batch never reaches the optimizer** (issue #371). Mini-batch ids come
  from **train** (`skillopt.py:230`) but filter the parent's **val** rows
  (`skillopt.py:291` → `harness.py:2011-2012`; also `:315`, `:319`), and splits are
  disjoint slices (`splits.py:117-119`). Every step renders `0 solid / 0 flaky /
  0 failing of 0 tasks` with no task ids, and `## Failure patterns still unsolved`
  never appears — while the `(mini-batch of N train tasks, L=…)` label still
  prints, which is why it looked healthy. Until #371 lands the per-step signal is
  the label plus the `L` sentence, so the epoch/mini-batch structure is
  bookkeeping rather than focus. PR #370 fixed the same defect in hill-climb's
  `cyclic`/`hardest-first` modes.
- **The epoch-boundary re-evaluation scores the whole train split, not a sample.**
  `skillopt.py:458-463` calls `evaluate_candidate(..., split="train")` twice with
  no `ids=`, then discards everything outside the ~20 sampled ids
  (`:464-466`). Budget it as `2 × len(train) × n_trials` rollouts per boundary.
- **When an epoch accepted nothing, the comparison is vacuous.** The re-eval is
  guarded by `prev_epoch_best_id != run_dir.best_id` (`skillopt.py:455`); if
  nothing moved, both sides stay `current_val` — the same list — so 0 regressed
  and 0 improved are reported over **val** tasks while the log line claims a
  train sample size (`:469-470`). The consolidation step still runs.
- **`requested_edits` vs `applied_changes` surfaces nothing.**
  `_changed_components` (`skillopt.py:398-427`) counts files whose bytes differ,
  not edits, and `applied_changes` is written at `:338`/`:345` and read nowhere —
  no dashboard column, no check, no warning. A run at `L=4` logged
  `applied_changes: 6` with no consequence.
- **"skill" leaks into the live prompt.** `skillopt.py:147` tells the optimizer to
  compare "the skill" regardless of which capability is under optimization. An
  algorithm must be capability-agnostic; this text is not.

## Key flags

`--epochs`, `--batch-size`, `--accumulation` (mini-batches per step; multiplies
the effective batch), `--edit-budget` / `--min-edit-budget` / `--lr-schedule`,
`--slow-update-sample`, `--no-slow-update`. `--resume`, `--no-regression`,
`--n-trials`, `--workers`, `--gate-mode`, `--k-se`, `--protected-paths`,
`--store` behave as in hill-climb.

`--max-iterations` is accepted and **ignored** — the loop is epoch-driven, so
`cap-evolve run`'s iteration cap has no effect here (`scripts/run.py:42-43`, whose
help text now says so). Control the step count with `--epochs`/`--batch-size`.

```bash
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --epochs 4 --batch-size 8 --accumulation 1 \
  --edit-budget 4 --lr-schedule linear --min-edit-budget 2 --n-trials 4
```

Requires `baseline.json` first, like its sibling algorithms.

## References
- `references/concepts.md` — the loop step by step, the schedule shapes with
  worked values, and the buffer / consolidation mechanics. Load it when you need
  to change the loop or reason about its rollout cost, not to run it.
