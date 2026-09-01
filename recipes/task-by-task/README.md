# Task-by-task experiment — recipes

One cap-evolve project per SkillsBench task: single-task split (train=val=test=[that
task]), `num_trials=10` for a tight paired standard error, small per-task budget. Sourced
from `intake_skillbench_c2` (43 tasks) and `intake_skillbench_c3` (44 tasks) — the two
worktrees split the 87-task fleet with no task overlap between them.

- **`<task>/capevolve.<task>.yaml`** + **`split_ids.<task>.json`** — the task-specific
  recipe and split. This is what changes per task.
- **`_shared/`** — `adapters/adapter.py`, `adapters/anthropic_env.py`,
  `optimizer/INSTRUCTIONS.md`, `PROJECT.md`. Byte-identical across every one of the 87
  project dirs (verified via md5sum before dropping the duplicates) — copy `_shared/`
  alongside any per-task dir to reconstruct a runnable `.capevolve/project_<task>/`.

## Selecting which run backs each task

Several tasks in `c2` were retried multiple times (`_v1` through `_v5`) after
infrastructure issues (`LOCK_TIMEOUT`, `STALE_cand_data`, `OLD_ANTHROPIC_KEY`,
`infra_broken_uvx`, `CORRUPTED_batch3`). For each task, the harvest picked the
highest-numbered run *not* tagged with one of those failure suffixes (falling back to the
highest-numbered run overall if every attempt failed). `c3` had two tasks
(`fix-build-agentops`, `setup-fuzzing-py`) with a pre-bugswarm-patch `INFRA_BROKEN` attempt
alongside a later clean one — the clean one was picked. See
`../../artifacts/task-by-task/MANIFEST.json` for the exact `(task, source worktree, run
dir, best_id, iterations spent)` used for every one of the 87 tasks.

To rerun a task: copy its `capevolve.<task>.yaml` + `split_ids.<task>.json` and `_shared/`
into a fresh `.capevolve/project_<task>/`, drop in a `seed_capability/` (see
`../../artifacts/task-by-task/<task>/seed/`), point `runner_repo_path` at a local
`vendor/skillsbench` checkout, and run `cap-evolve run capevolve.<task>.yaml`.
