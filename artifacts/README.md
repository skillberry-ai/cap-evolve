# artifacts/

The `seed`/`best` skill-package snapshots produced by the recipes in `../recipes/` —
what actually changed, not just the config that produced it. Organized to mirror
`recipes/`, one subdirectory per experiment configuration.

- `all/` — shared seed for both "all"-family variants, plus the one accepted candidate
  (from the 43-task runnable-subset run; the pure 87-task recipe never got past seed).
- `task-by-task/` — per-task `seed/` + `best/` (87 tasks; see `task-by-task/MANIFEST.json`
  and `task-by-task/README.md` for which tasks have no `best/`).
