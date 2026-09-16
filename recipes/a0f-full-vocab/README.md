# recipes/a0f-full-vocab/

Arm **A0f** — one project per task, `capability_path` pointed at the shared 196-skill union
(`.capevolve/seed_capability_full196`) instead of the task's own seed skills, `max_iterations: 0`
(pure baseline eval, no optimizer loop). 10 of 87 tasks are recipes here so far; results for
these 10 are in [`../../results/a0f-full-vocab/`](../../results/a0f-full-vocab/). The remaining
77 tasks get their own subdirectory here as they're run — same pattern, just point
`capability_path` at the same shared library and swap in that task's id.

See [`../../docs/specs/experiments_plan_v1.md`](../../docs/specs/experiments_plan_v1.md) for
what this arm measures and why.
