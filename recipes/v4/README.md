# recipes/v4

The cap-evolve project config every T2 (`v4_t2_e1`) run used — copied verbatim, one shared
template rather than 21 near-duplicates.

## What's here

- **`capevolve.yaml`** — the *entire* per-task project config, byte-identical across all 21
  optimized tasks except the header comment naming the task (confirmed via `diff` against a second
  task, `cloud-024-guid-to-account`, during this doc's writing). Copied from
  `platform-005-wrong-owner-trap`'s project only because that's the task this doc's author happened
  to check first — nothing else about that task is special.
- **`split_ids.json`** — one representative copy. Every task's real file is generated from the same
  template with its own task id substituted into all three splits: `train == val == test == [that
  task]`. This is a **deliberate single-task-tuning design**, not an accidental degenerate split —
  contrast v1, where an empty `split_ids_file` caused an *unintended* random draw (see
  `../v1/README.md`). There is no held-out test split this phase; `results/v4/summary.md`'s
  data-quality caveat #3 explains what `test` means here anyway (same task, later time step, not a
  disjoint task set).
- **`INSTRUCTIONS.md`** — the optimizer's own instructions template (9 `{{...}}` placeholders filled
  in per-run: target reader, failure summary, empty-seed flag, failing/passing task lists, the
  system-prompt-only capability brief, the hill-climb algorithm brief, the benchmark repo path, and
  a single-lane parallelism note). **This is deliberately vendored here, unlike v1/v2's recipes**,
  whose top-level `../README.md` states "No optimizer instructions... cap-evolve's own file, not a
  parsec artifact" — that's true for v1/v2, which used cap-evolve's generic default. v4's template
  is not the default: it was authored specifically for this project (the "no tools/code layer"
  capability scope, the "choose the lever by failure type" decision guide, the non-overfitting
  warning), so it is parsec-v4-specific content and belongs here.

## Recipe vs. run: no divergence found

Unlike v1 (3 documented mismatches — see `../v1/README.md`) and v2, this template's declared budget
values were checked against two tasks' actual recorded state and matched exactly:

| task | run | `state.json` budget | matches `capevolve.yaml`? |
|---|---|---|---|
| `platform-005-wrong-owner-trap` | `run_20260920_103719` | `max_iterations=3, max_usd=50.0, stall=2, max_optimizer_usd=20.0, stop_at_reward=1.0` | yes |
| `cloud-024-guid-to-account` | `run_20260919_122425` | `max_iterations=3, max_usd=50.0, stall=2, max_optimizer_usd=20.0, stop_at_reward=1.0` | yes |

This is expected, not a coincidence: unlike v1/v2's hand-written yaml, v4's per-task
`capevolve.yaml` is programmatically rendered by
`scripts/v4_t2_e1/scaffold_projects.py::render_capevolve_yaml()` in the `parsec-intake_v4`
worktree, so there is no hand-editing step where it could drift from what actually ran.

## The real execution plan

The mechanism that built the 21 per-task projects and ran them one at a time — the harbor adapter,
the `TASK_ID`-env-var-driven candidate injection into the live `parsec-live` clone, the single-lane
"one task, start to finish, then the next" runner design, and the 6 deviations found while building
it against the original spec — is documented in full in the `parsec-intake_v4` worktree (not this
branch, since it's source code, not a result narrative):

```
parsec-intake_v4/docs/superpowers/plans/2026-09-17-parsec-v4-task-by-task-optimization.md
```

This is the `v4_t2_e1` equivalent of what `v1/PROJECT.md` and `v2/PROJECT.md` are for their
experiments — read it before rerunning or extending T2, or before designing C2/G2 (which will reuse
this same adapter and single-lane-runner shape, scaled from 1 task per run to N).

## What is deliberately not here

Same exclusions as `../README.md` documents for v1/v2 (no `.env`, no task definitions — v4's tasks
are defined by the harbor `parsec` benchmark plugin added in PR #495, not by a per-experiment
`tasks.json`, since this is a first-class harbor benchmark rather than a trace-extracted or
hand-authored one-off), **except** `INSTRUCTIONS.md`, which is vendored here for the reason given
above.

## No `seed_capability/` here

The seed bundle every task's optimizer started from lives in
[`../../artifacts/v4/seed/`](../../artifacts/v4/seed/), not duplicated under `recipes/`, matching the
v1/v2 convention.
