# Task-by-task experiment — artifacts

Per-task `seed/` and `best/` skill-package snapshots, one directory per SkillsBench task
(87 total). See `MANIFEST.json` for exactly which run store and candidate each task's
`seed/`/`best/` came from (source worktree, run dir, `best_id`, iterations spent).

- **`<task>/seed/`** — the task's own starting skills (copied from the task's
  `environment/skills/` at project-creation time), present for all 87 tasks.
- **`<task>/best/`** — the accepted candidate cap-evolve's optimizer settled on
  (`state.json`'s `best_id`), present only when optimization actually improved on the
  seed. **35 of the 87 tasks have no `best/` dir** — the optimizer never accepted a
  candidate, either because the seed was already saturated at the ceiling (`val=1.0`, no
  headroom — see `[[feedback_saturated_baseline]]`) or because CCC infrastructure errors
  held the task at its `val=0.0` baseline for the whole run. `MANIFEST.json` distinguishes
  the two: iterations spent but `best_id: "seed"`.

`__pycache__/` and `.pyc` files excluded throughout (evidence of execution, not part of
the artifact).
