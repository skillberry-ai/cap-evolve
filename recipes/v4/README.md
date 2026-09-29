# recipes/v4

Two arms have run against the same 34 v4 tasks so far — T (task-by-task) and G (global, shared
bundle). This directory holds what's shared between them, plus a per-arm subdirectory for what
differs.

## What's shared

- **`INSTRUCTIONS.md`** — the optimizer's own instructions template (9 `{{...}}` placeholders filled
  in per-run: target reader, failure summary, empty-seed flag, failing/passing task lists, the
  system-prompt-only capability brief, the hill-climb algorithm brief, the benchmark repo path, and
  a single-lane parallelism note). **This is deliberately vendored here, unlike v1/v2's recipes**,
  whose top-level `../README.md` states "No optimizer instructions... cap-evolve's own file, not a
  parsec artifact" — that's true for v1/v2, which used cap-evolve's generic default. v4's template
  is not the default: it was authored specifically for this project (the "no tools/code layer"
  capability scope, the "choose the lever by failure type" decision guide, the non-overfitting
  warning), so it is parsec-v4-specific content and belongs here. It stays at this level, not
  per-arm, because the **G project symlinks straight back to it**
  (`optimizer -> ../../../scripts/v4_t2_e1/common/optimizer`, `adapters -> …/common/adapters`) — G
  reused T's optimizer scaffolding verbatim rather than authoring its own.
- **The seed bundle** every arm hill-climbs from lives in
  [`../../artifacts/v4/seed/`](../../artifacts/v4/seed/), not duplicated under `recipes/`, matching
  the v1/v2 convention.

## Per arm

- **[`v4_t_e1/`](v4_t_e1/)** — T's `capevolve.yaml` (one shared template rendered per task, 21
  near-identical copies collapsed to one) and `split_ids.json` (single-task tuning, one task per
  run).
- **[`v4_g_e1/`](v4_g_e1/)** — G's `capevolve.yaml` (one config for a single run-wide optimization
  across all 34 tasks, with a documented post-run divergence from what actually ran — see that
  README) and `split_ids.json` (all 34 tasks, no holdout).

## What is deliberately not here

Same exclusions as `../README.md` documents for v1/v2 (no `.env`, no task definitions — v4's tasks
are defined by the harbor `parsec` benchmark plugin added in PR #495, not by a per-experiment
`tasks.json`, since this is a first-class harbor benchmark rather than a trace-extracted or
hand-authored one-off), **except** `INSTRUCTIONS.md`, which is vendored here for the reason given
above.
