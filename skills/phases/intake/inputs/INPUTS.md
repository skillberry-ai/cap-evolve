# Inputs for a cap-evolve run (collected by `intake`)

For every **NEEDED** input that is missing, ASK THE USER — quote the expected
path, how to obtain it, and the alternatives. Never invent a NEEDED input.
**RECOMMENDED** inputs have sane defaults; note any you skip in `PROJECT.md`.

## NEEDED  (the run cannot proceed without these)

- **tasks dataset**: the evaluation tasks (each with an id and a gold/criterion).
  - where: `examples/<bench>/tasks.jsonl` or your benchmark's export
  - how to get it: export from your benchmark, or return them from the adapter's
    `tasks(split)`; one JSON object per line `{"id","input","target",...}`
  - options: a `.jsonl` file | a directory of json | `"adapter"` (tasks() builds them)

- **target agent (RUNNER)**: the agent under test + how to run it on a task.
  - where: implemented in `.capevolve/project/adapters/adapter.py::run_target`
  - how to get it: wire your agent's entrypoint (CLI/SDK/HTTP) inside `run_target`;
    capture output + trace into a `Rollout`
  - options: in-process call | subprocess | a benchmark's own runner (`run_batch`)

- **scorer**: how a rollout becomes a reward in [0,1] + feedback.
  - where: `adapter.py::score`
  - how to get it: exact-match / state-check / rubric; feedback must be general
    (never leak the gold answer)

- **capability artifact**: the thing being optimized (a copy is edited).
  - where: a dir/file, e.g. `policy/policy.md`, `tools.json`, a skill package dir
  - capability skill: `system-prompt | tools | mcp-tool | skill-package | …`

## RECOMMENDED  (defaults shown; override in capevolve.yaml)

- **splits** — `train` / `val` / `test`.
  - default: seeded ratio split `0.5 / 0.25 / 0.25` (`split_seed`, `split_train/val/test`)
  - pin explicitly: `split_ids_file` → JSON `{"train":[],"val":[],"test":[]}`
    (use a benchmark's official split, or set all three equal to fit the whole set
    with **no holdout** — the report will flag the test number as a fit metric)
  - guidance: enough tasks to split three ways; **test is sealed** (scored once).

- **num_trials** (default 1): trials per task. Use ≥3–4 for stochastic agents —
  single-trial scores are noisy and the significance gate will (correctly) reject
  marginal gains. Enables pass^k / pass@k.

- **budget**: `max_iterations` (default 10), `stall` (stop after N rejects),
  `max_metric_calls` (0 = unlimited), `max_usd` (0 = unlimited; total cap over
  runner + optimizer + intake), `max_optimizer_usd` (separate optimizer-only cap),
  and `optimizer_max_turns` (per-iteration cap passed to the agent CLI, e.g.
  claude-code `--max-turns`). Write all of these into `capevolve.yaml` — the template
  has slots for each. Suggest the user run `cap-evolve estimate --spec capevolve.yaml`
  to preview call counts and a $ range before the first run.

- **optimizer + model**: `optimizer_skill` is the optimizer NAME, resolved by the
  `run-optimizer` skill against `optimizers/registry.yaml` (run `run-optimizer --list`
  to see the available names); `optimizer_model` is the backend-specific model id.

- **gate**: `gate_mode` (significant|strict|threshold|simplicity_tiebreak),
  `gate_k_se` (default 1.0). Add `--no-regression` to forbid breaking passing tasks.

- **baseline traces** (optional): prior rollouts to seed diagnosis. Default: none
  (the baseline phase produces them on the first val eval).

## Notes
- The intake script scaffolds `.capevolve/project/` from the template; fill the
  adapter + `capevolve.yaml`, then run `cap-evolve check` (the hard gate).
- Paths are relative to the project working dir unless absolute.
