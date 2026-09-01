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

- **scorer**: how a rollout becomes a reward in [0,1] + ARGUMENT-LEVEL feedback.
  - where: `adapter.py::score`
  - how to get it: exact-match / state-check / rubric for the reward.
  - **feedback is the learning signal — make it ARGUMENT-LEVEL and gold-SAFE.**
    A tool-name-only signal ("action X was wrong") is too coarse for the optimizer to
    localize a fix — it can only pattern-match to prose rules and plateaus. For EACH
    failing check, the feedback MUST localize the defect:
    - name the wrong ARGUMENT key and the **AGENT'S OWN wrong value** (NOT the gold
      value) — e.g. `"<tool>: arg <key>=<agent's value> is invalid"`;
    - name the wrong TARGET id when a write acted on the wrong entity — e.g.
      `"<tool>: called on <agent's target> but the task targets a different one"`;
    - for communication / omission misses, name the value or field the agent FAILED
      to state **when it is derivable from the agent's own state** (e.g. a computed
      total it could have summed from its own observed amounts).
  - **gold-SAFE (the hard constraint):** never read or print the gold/expected
    value. Derive everything from the AGENT'S OWN messages/tool-calls/observed state
    (and the user's own profile/db state the agent saw). Use the gold record ONLY to
    learn WHICH check/argument failed (key names are safe; values are not). If a piece
    is not safely derivable, fall back to the coarser tool-name message.
  - **deterministic:** `score()` must be deterministic on a fixed rollout (the
    `cap-evolve check` gate enforces this) — derive feedback from the rollout, do not
    call out to an LLM or use randomness.

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

- **memory_skill** (default `md-files`): which cross-iteration memory scheme the
  optimizer reads/writes. `md-files` is `harness.py`'s built-in LEDGER/JOURNAL/
  INSIGHTS/META_INSIGHTS/FRAMEWORK_IMPROVEMENTS scheme (always on today — every run
  gets it regardless of this key) and is the only fully-wired option; note the choice
  in `PROJECT.md` either way. The deprecated `evograph` algorithm's `wiki/` weakness-
  graph format is a candidate SECOND option once it is extracted into a standalone
  memory skill (tracked separately — not selectable yet).

- **target_model** (default `""` = profile-agnostic): the runtime/CONSUMING LLM the
  agent reads these capabilities with — DISTINCT from `optimizer_model`, which proposes
  the edits. Give a concrete model id (e.g. `gpt-oss-120b`) or a capability tier
  (`frontier | strong | mid | weak`). cap-evolve steers the optimizer prompt and the
  capability guidance to optimize FOR this reader (a weaker reader gets more explicit
  rules, worked examples, and code enforcement; a frontier reader gets leaner prose that
  explains the *why*). ASK the user which model the agent runs at runtime; if unknown,
  leave blank and note it in `PROJECT.md`. Optionally set `target_profile_file` to a raw
  text/markdown file to override the resolved tier's built-in brief.

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
  per-iteration optimizer-prompt TEMPLATE. The scaffold already copies a generic default
  to `project/optimizer/INSTRUCTIONS.md` — the agent CUSTOMIZES that file rather than
  authoring one from scratch, and points this key at it. Three jobs, no re-authoring of
  what the template already says (depth mandate, non-overfitting guardrail, STEP-0
  reading mandate, cross-iteration file protocol):
  - keep every `{{...}}` placeholder intact — the harness fills them per iteration, and
    `implement-and-check`'s pipeline self-test fails if one is deleted;
  - **scope it to the SELECTED capabilities** — include guidance, skill references and
    editable artifacts only for the caps in `capevolve.yaml: capabilities`, so no run
    presents as editable an artifact it does not own. Each capability's own edit space
    lives in its `./guidance/<cap>/SKILL.md`; the failure taxonomy lives in
    `./guidance/diagnose/SKILL.md`; load `./guidance/<cap>/references/optimizer-playbook.md`
    for any selected capability that ships one;
  - add the benchmark facts the template cannot know: where the runner writes traces,
    what the scoring source is, which data-model files the capability's code imports.
  - **caution (issue #252):** a *relative* value here resolves project-relative under
    `cap-evolve check` but cwd-relative under `cap-evolve run`, which then silently falls
    back to the generic template. Write it absolute, or verify `run` picks up the
    customized file.
- **gate**: `gate_mode` (**paired** recommended — per-task paired SE on the same tasks
  both sides, ~2-3x smaller than combined-SE `significant`, so real 1-task gains bank;
  also: significant|strict|threshold), `gate_k_se` (default 1.0; the
  examples use 0.2). Add `--no-regression` to forbid breaking passing tasks.

- **metrics (display)**: which numbers to surface and which one GATES.
  - `metric_primary`: the single metric that decides accept/reject (= the scalar reward). Blank = use the reward directly.
  - `metrics_display` + `metric_directions`: extra SHOWN-ONLY metrics and each one's direction (`higher`|`lower`). These never affect the gate — display only.
- **github_integration** (default `false`): if `true`, intake runs `gh auth status`; when authed, cap-evolve may mirror the algorithm's work items as issues and ship the winner as a PR (`Closes #n`). WHAT gets mirrored is algorithm-specific — the chosen `algorithm_skill` defines it (e.g. evograph mirrors *weaknesses*; a candidate-based algorithm might mirror candidates/iterations). GitHub is NEVER the source of truth — the run dir is. If unauthed, intake offers `gh auth login` or skip.
- **orchestration_mode** (default `deterministic`): `deterministic` = cap-evolve sequences the loop (code-enforced honesty). `agent` = the coding agent drives the loop via cap-evolve primitives and seals with the finalize phase script (`skills/phases/finalize/scripts/run.py`). Agent mode also uses `stop_condition`.
- **stop_condition** (default empty): agent-mode free-text halt rule, re-read each round. Deterministic mode ignores it and uses the budget knobs.

- **baseline traces** (optional): prior rollouts to seed diagnosis. Default: none
  (the baseline phase produces them on the first val eval).

## Notes
- The intake script scaffolds `.capevolve/project/` from the template; fill the
  adapter + `capevolve.yaml`, then run `cap-evolve check` (the hard gate).
- Paths are relative to the project working dir unless absolute.
