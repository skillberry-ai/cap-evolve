# recipes/

The cap-evolve project configs a rerun needs — the `capevolve*.yaml`, the pinned split file, the
`PROJECT.md` decision log, and (for v2) the task-patching script. **Copied verbatim** from the two
source worktrees, one subdirectory per experiment. Paired with [`../artifacts/`](../artifacts/): a
recipe reruns the experiment from scratch, the artifact is what the run actually produced.

| directory | experiment | files |
|---|---|---|
| [`v1/`](v1/) | 30 trace-extracted `traces_parsec-aap2-*` tasks | `capevolve.yaml`, `splits.json`, `PROJECT.md` |
| [`v2/`](v2/) | 10 hand-authored `bench-aap2-*` tasks | `capevolve.v2.2.yaml`, `splits-v2.2.json`, `PROJECT.md`, `patch-harbor-tasks-v2.1.sh` |

## Read the per-directory README before rerunning either

These are verbatim copies, which means they are **also a record of what the recipes got wrong**. In
both experiments the committed yaml disagrees with what the run actually did — v1's in a way that
would silently change the experiment (`split_ids_file` is empty, so a rerun draws a random split
instead of the pinned two tasks), v2's in a way that misdescribes it (comments carried over from v1
that document a different task count, a different split shape, and a different scoring formula).
Neither file was edited to look better. [`v1/README.md`](v1/README.md) and
[`v2/README.md`](v2/README.md) list every divergence found, with the source of truth for each.

## What is deliberately not here

- **No `.env`.** Both source worktrees have one (600-perm, gitignored) holding gateway credentials
  and the LiteLLM base URL. `v1/PROJECT.md` documents the variable *names*; no value is in this
  branch. This branch has no `.gitignore` inherited from `main` for most of its history — a
  minimal one is committed at the root — so check `git status` before staging anything new here.
- **No `seed_capability/`.** The seed skill package the recipes point at lives in
  [`../artifacts/v1/seed/`](../artifacts/v1/seed/) and [`../artifacts/v2/seed/`](../artifacts/v2/seed/)
  rather than being duplicated under `recipes/`.
- **No optimizer instructions.** Both yamls reference `optimizer/INSTRUCTIONS.md`, which is
  cap-evolve's own file, not a parsec artifact.
- **No task definitions.** The harbor task directories (`harbor-tasks/`, `harbor-tasks-v2.1/`) are
  hundreds of files. Every contract that any number in this branch depends on is committed in
  machine-readable form instead: [`../results/v1/tasks.json`](../results/v1/tasks.json) and
  [`../results/v2/tasks.json`](../results/v2/tasks.json).

## To rerun

Both recipes assume a live simulator fleet, which is the part a recipe cannot capture. v1 needs
four kaegis endpoints (aap2 `:8086`, github `:8087`, babylon `:8088`, provisions_db `:8090`) — and
**25 of its 30 tasks were scored while only the first two were up**, which is the single most
important fact in [`../results/v1/summary.md`](../results/v1/summary.md). v2 needs one kaegis process
per task (`:9086`–`:9095`), each seeded from that task's own `seed.json`.
