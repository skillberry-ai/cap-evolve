# recipes/

cap-evolve project configs (the `capevolve.*.yaml` + `split_ids.*.json` a rerun needs),
organized one subdirectory per experiment configuration. Paired with `../artifacts/` (the
`seed`/`best` skill packages those recipes produced) — a recipe alone reruns the
experiment from scratch; the paired artifact is what it actually produced.

- `all/` — the two "sweep everything" variants: the full 87-task recipe (stalled at seed)
  and the derived 43-task runnable-subset recipe (reached an accepted candidate).
- `task-by-task/` — one project per SkillsBench task, 87 in total.

Train-test-split recipes are not yet harvested here — that experiment is still running.
