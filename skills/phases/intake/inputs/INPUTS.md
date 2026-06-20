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
  - **runner model + credentials**: which model(s) the runner uses and the env vars /
    `.env` keys it needs (e.g. `OPENAI_API_KEY`, `WATSONX_*`, `RITS_API_KEY`). For an
    OpenAI-compatible / custom endpoint (vLLM, IBM RITS, a gateway), capture the
    `api_base` + any custom auth header and pass them through the runner's LLM config
    (most benchmarks forward extra kwargs to litellm) — prefer per-call config over
    monkeypatching. ASK the user for missing credentials; never hardcode a secret.
  - **benchmark repo (if the runner IS a benchmark)**: where to get it (a local path
    or git URL) and how to install it (e.g. `pip install -e ../<bench>`). Record the
    resolved commit so the run is reproducible.

- **scorer**: how a rollout becomes a reward in [0,1] + feedback.
  - where: `adapter.py::score`
  - how to get it: exact-match / state-check / rubric; feedback must be general
    (never leak the gold answer)

- **metric extraction / scoring source**: WHERE the objective metric lives, so
  `score()` can be implemented AND verified against the benchmark's own number.
  - where: a reference to the benchmark's scoring implementation (file/function/CLI)
    OR a precise description of how the metric is read out of one trajectory (which
    field/file in a native trace holds pass/fail or the graded reward)
  - how to get it: point at the runner's scorer (`<bench>/.../score.py`, a results
    `metrics.json` key, a rubric spec) or describe the read path ("trajectory's
    `reward` field", "the `outcome=="success"` line of the result json")
  - why: without this the intake agent cannot write a faithful `score()` — a guessed
    scorer produces a number that does not match the benchmark and the run is wasted

- **trajectories path**: the DIRECTORY the runner writes its native traces/results
  to for an eval (any structure, any format — JSON, logs, per-task subdirs).
  - where: returned by the intake-authored `adapter.trajectories(split)`; the path
    itself comes from your runner config (e.g. the runner's `--output-dir`/log dir)
  - how to get it: run one eval and note where the runner dumps its traces; return
    that `Path` from `trajectories(split)` (return `None` to fall back to cap-evolve's
    own per-rollout JSON)
  - why: cap-evolve copies this directory **verbatim** into the optimizer's working
    dir as `./trajectories/`, so the optimizer reads the FULL, unmodified traces (not
    a lossy summary) when proposing edits. This is the optimizer's ground truth.

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
  runner + optimizer + intake), `max_optimizer_usd` (cumulative optimizer-only cap),
  `optimizer_max_turns` (per-iteration WORK cap passed to the agent CLI, e.g.
  claude-code `--max-turns N`), and `optimizer_usd_per_iter` (per-iteration DOLLAR cap
  passed to the agent CLI and enforced by it where supported, e.g. claude-code
  `--max-budget-usd N`; optimizers without a native $ cap, e.g. ibm-bob, ignore it and
  rely on `optimizer_max_turns` / `max_optimizer_usd`). Write all of these into
  `capevolve.yaml` — the template has slots for each. Suggest the user run
  `cap-evolve estimate --spec capevolve.yaml` to preview call counts and a $ range
  before the first run.

- **optimizer + model**: `optimizer_skill` is the optimizer NAME, resolved by the
  `run-optimizer` skill against `optimizers/registry.yaml` (run `run-optimizer --list`
  to see the available names); `optimizer_model` is the backend-specific model id.

- **runner_repo_path** (default `""`): the benchmark/runner SOURCE (a local path or
  checkout), surfaced to the optimizer as READ-ONLY context so it can consult the
  runner's tools / scoring / task structure while proposing edits. Set it when the
  runner is a benchmark repo; leave empty if there is no separate source to read.

- **capability_sources** (default `[]`): extra source files — the benchmark's
  data-model / types module(s) that a selected capability's code imports — copied
  VERBATIM into the optimizer's `./guidance/sources/` so it can write correct code
  against the real types. Resolved relative to the project dir (or capability dir).
  - how to get it: look at what the seed capability's code imports (e.g. the tools
    file's `from <bench>.data_model import ...`) and list those module paths.
  - set it whenever a selected capability edits code against a shared types module;
    leave `[]` when there is no such source.

- **optimizer_instructions_file** (default `optimizer/INSTRUCTIONS.md`): the
  per-iteration optimizer-prompt TEMPLATE. The scaffold already copies a generic
  default to `project/optimizer/INSTRUCTIONS.md`; the agent CUSTOMIZES it for this
  benchmark (keeping the `{{...}}` placeholders the harness fills) rather than
  authoring one from scratch. Point this key at the customized file. Keep the
  authored guidance short on meta-narration but explicit and DEMANDING on iteration
  depth, with an explicit GOAL (maximize the eval score). The authored instructions
  must impose a DEPTH MANDATE — each iteration is a substantial multi-cluster,
  multi-edit-class sweep (tool code + validation + enriched returns + new tools +
  many docs + prompt), non-regression scoped per fix; a single small edit is an
  under-used iteration. Produce this target snippet: "Each iteration is a
  substantial, multi-root-cause pass. Diagnose ALL clusters and fix as many as
  possible in ONE candidate — improve multiple tools' code, validation, and return
  values/errors; add new tools; sharpen many tool docs; and fix the prompt —
  together. Scope each fix to protect passing tasks; do NOT trade breadth for
  caution. A single small edit is an under-used iteration." And **scope it to the
  SELECTED capabilities only** — include guidance / skill-references / editable
  artifacts for just the caps in `capevolve.yaml: capabilities`. If only `tools` is
  selected, do NOT include prompt-editing guidance, do NOT reference the
  `system-prompt` skill, and do NOT present the prompt file as editable (and vice
  versa). The authored instructions must also direct the optimizer to: READ and USE
  the selected capability skills (`./guidance/<cap>/SKILL.md`), the diagnose skill
  (`./guidance/diagnose/SKILL.md`), its own features reference
  (`./guidance/optimizer/<name>.md`), and any `./guidance/sources/` files; READ
  `./MEMORY.md` FIRST and never re-propose an approach recorded as
  rejected-as-implemented (not a permanent ban); understand the prior-iteration
  run-dir layout; write the rich `## Handover for next iteration` STATE.md section;
  and address ALL failure clusters each iteration (parallel subagents → merge into
  one candidate where supported). See intake SKILL.md step 5.

- **gate**: `gate_mode` (significant|strict|threshold|simplicity_tiebreak),
  `gate_k_se` (default 1.0). Add `--no-regression` to forbid breaking passing tasks.

- **baseline traces** (optional): prior rollouts to seed diagnosis. Default: none
  (the baseline phase produces them on the first val eval).

## Notes
- The intake script scaffolds `.capevolve/project/` from the template; fill the
  adapter + `capevolve.yaml`, then run `cap-evolve check` (the hard gate).
- Paths are relative to the project working dir unless absolute.
