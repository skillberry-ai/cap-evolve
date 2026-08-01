# Changelog

All notable changes to cap-evolve are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

## [Unreleased]
### Fixed
- **Sandbox containers were never released, and the leftovers ran forever.** The vendored
  server reclaims a container only on a hardcoded 10-minute idle timeout
  (`api.py`'s `KERNEL_TIMEOUT`) or on a force-cleanup at SIGINT, and nothing released a
  kernel when its rollout ended — every rollout mints a fresh `conv_id`. At 8-way
  concurrency that leaves ~50 containers alive at all times, and the ones still alive when
  the server is asked to stop are stopped **serially** inside the adapter's flat 60s
  shutdown budget: whatever the budget doesn't reach is orphaned and then runs forever,
  because the only process that knew about it is gone. Run 30691123806 left **176**
  `conv-capevolve-*` containers running on the self-hosted runner (all "unhealthy", load
  average 14), with `ConnectionRefusedError: Failed to reconnect to kernel websocket`
  throughout its sandbox log — at three full seeds (2,279 rollouts each) that is a
  runner-health problem, not a cosmetic one. The adapter now releases each rollout's
  container in a `finally`, so the live count tracks concurrency instead of run length, and
  the shutdown budget scales with however many are actually left (~0 now) instead of being a
  flat 60s. Done **without touching `third_party/`** — that directory is a filtered subtree
  which must stay byte-identical to upstream for `git subtree pull` to work, so the adapter
  serves a small wrapper that imports the vendored `ExecuteHandler`/`cleanup_kernels`
  unchanged and adds `/release` (plus `/health`, which is what lets shutdown size its
  budget). Verified live on the runner: container created → released → `live_kernels: 0` →
  shutdown in 0.1s with nothing left to stop.
- **The 912-task dataset's own top-level directory locked the sandbox out of everything.**
  The upstream `spreadsheetbench_912_v0.1.tar.gz` stores its top-level dir as `drwx------`
  (the 200-task sample stores `0755`), and `tar` preserves stored modes. The adapter
  bind-mounts exactly that dir at `/mnt/data` in a container running as uid 1000, so a
  non-traversable root makes every path under the mount unreachable — **reads too, not just
  writes**: `open()` on an input workbook and even `Path.exists()` raise `EACCES`, because a
  missing search bit is not a missing file. Only the `full`/`pilot` tiers were affected;
  `smoke` uses the 200-task sample. Pilot run 30691123806 spent **$77.49 and ~3h** to
  discover this, scored 0.000 across 50 tasks with an EACCES traceback in all 50 rollouts,
  and blamed "the output dir is not writable" — a diagnosis that costs hours, because the
  output dir was fine and so were `spreadsheet/` and the workbooks (0755/0644). Fixed at
  three levels: `fetch_data.sh` normalizes modes on extract (`chmod -R a+rX` — traverse and
  read only; the dataset is read-only INPUT) and re-normalizes the root for trees cached by
  an older revision; the adapter widens the root it can own and then **verifies the mount
  before the first LLM call** (`_preflight_mount`), so an unusable mount aborts in seconds at
  ~$0 instead of burning a full eval; and the denial classifier now recognizes denied
  *reads* anywhere under the mount and reports the traverse fault distinctly from the
  output-dir fault, since the two need different fixes.
- **The optimizer was told to edit `tools.py` on a benchmark that has no tools.** The shared
  `templates/project/optimizer/INSTRUCTIONS.md` is written for a capability that includes
  tool CODE: it instructs "prefer code", names `tools.py` and tau2's `get_*_details`, and its
  self-check demands "edits across BOTH policy.md AND tools.py". SpreadsheetBench's
  capability is `[system-prompt]` — a single `prompt.md` — so that guidance contradicts the
  correctly-rendered "what you are editing" block and sends the optimizer hunting for code.
  In run 30691123806 it found some: `cand_0002` scored 0.567 by patching **`adapter.py`** to
  chmod the data root while leaving `prompt.md` byte-identical to the seed, so that run's
  apparent 0.000 → 0.567 gain was infrastructure repair, not capability. A prompt-only
  instructions template (`INSTRUCTIONS.prompt-only.md`) now ships alongside the default:
  prompt-appropriate levers (output contract, ordered/unavoidable step, worked method,
  narrowing predicate, consolidation), an explicit boundary that the adapter/harness/scorer
  are not editable, and a rule that an ENVIRONMENT fault is to be *diagnosed and handed
  back*, not worked around. `run_suite.sh` selects it for the spreadsheetbench arm at the
  path `cli.py` already defaults to, and additionally pins it by ABSOLUTE path — a relative
  `optimizer_instructions_file` resolves against different cwds in check vs run and can
  silently fall back to the generic template (#252), which would erase this fix with no
  error. That spec line is empty (a verified no-op in both the PyYAML and the fallback
  parser) for every other benchmark, so no `core/` change was needed and tau2's
  code-bearing guidance is untouched.
- **A running `pilot` leg was invisible on the benchmarks page.** `site/benchmarks.js`'s
  `JOB_RE` hardcoded `smoke|full`, so it never matched the `pilot / spreadsheetbench` job name:
  no "Running now" entry and no way to open the run's UI while it executed. Nothing errored —
  the run simply could not be seen. The tier is now matched generically (the bench allowlist
  stays explicit so "plan legs"/"aggregate history" still never match), and the history table's
  tier filter offers `pilot`. A test ties the site's matcher to the workflow's `TIERS` list so
  adding a tier cannot silently hide it again.

### Fixed
- **gpt-5.x rejected our temperature override, failing every rollout at $0.00 spend.** The
  gateway answers `400 Unsupported value: 'temperature' does not support 0.0 with this model.
  Only the default (1) value is supported.` — so run 30682720920 lost an entire pilot: all 60
  tasks errored on their first LLM call, the run finished in 9 minutes having billed nothing,
  and reported **success** with a clean-looking 0.000. `model_config` (shared by five adapters)
  now sends no `temperature` for model families that pin it, making the effective temperature
  the model's own default — 1 for gpt-5.x, the only value they accept. Safer than sending the
  value the error names, since a deployment may reject the parameter outright. A blank or
  `default`/`model`/`none` TEMPERATURE now also means "use the model default"; every other
  model still gets 0.0, so this is a no-op for tau2/swebench/skillsbench.
- **An infra-dominated run reported success.** Completion is not sufficient: a run whose every
  rollout died on infrastructure still writes `baseline.json`/`final.json`, records iterations,
  passes the gate, and publishes 0.000 to `benchmark-history` as though it measured something.
  `assert_run.py` now FAILS when more than `--max-infra-frac` (default 0.5) of baseline tasks
  are infrastructure errors, reusing `metrics.py`'s existing `_infra_task` rule — which already
  rendered those tasks as `⚠️ infra-error` in the report while the job went green. Verified by
  replaying run 30682720920's real `baseline.json`: the old gate exits 0, the new one exits 1.
  A genuine all-zero run with no infra errors still passes.

### Added
- **`pilot` tier — a cost/runtime measurement rig for SpreadsheetBench.** Answers the three
  things a ~$450 full run depends on and nobody has measured: cost and wall-clock per rollout at
  `MAX_TURNS=30` (every existing anchor is smoke at 5 turns, so it does not transfer), whether
  `azure/gpt-5.5` works on the gateway at all, and recalc throughput at non-trivial volume.
  60 tasks drawn **only from `full`'s train ids**, so `full`'s selection and test splits stay
  untouched. Its split is deliberately not 2:1:7 but 5/50/5 — `val` sized to be a solid anchor
  (full's is 91, so one pilot iteration extrapolates directly), `test` tiny because `finalize`
  evaluates it twice and teaches nothing new. **Pilot rewards are not comparable to anything**,
  which is why the tier is excluded from `tier=all`: the aggregate job publishes every leg to
  `benchmark-history` and sweeping it in would put meaningless rows on the benchmarks page.
- **Tiers are now populated per benchmark.** The planner only emits a leg when
  `ci/benchmarks/<bench>/<tier>/tasks.json` exists. `run_suite.sh` already no-opped on a missing
  file, but emitting the leg anyway claimed a slot on the single serialized self-hosted runner
  just to warn and exit — the waste the planner was introduced to remove. A partially-populated
  tier (only one benchmark ships `pilot/`) now costs the others nothing. Verified no-op: all 30
  pre-existing dispatch/label selections produce byte-identical legs.

### Added
- **SpreadsheetBench full tier can now produce a SkillOpt-comparable number.** Four gaps closed,
  all without touching `core/`:
  - **Held-out split.** A tier that commits `<bench>/<tier>/split_ids.json` now gets that exact
    disjoint split instead of the default no-holdout FIT split (`train == val == test`), so
    `finalize` yields a real generalization number rather than a fit. `full/split_ids.json` ships
    182/91/639 over all 912 tasks, generated by `spreadsheetbench/utils/make_split.py`, which
    reconstructs SkillOpt's *stated default* (`split_seed=42`, 2:1:7 — arXiv 2605.23904). Their
    SpreadsheetBench-specific split and task count are not published, so this is a documented
    reconstruction, **not** a reproduction; the tier README says so. The loader fails loudly on a
    split that overlaps, omits tier tasks, or has an empty val/test — a stale split silently
    evaluating a different task set would invalidate a whole comparison.
  - **Seeds.** `split_seed` is threaded into the generated spec (default 0 = previous behaviour).
    With a committed split the partition is fixed, so it varies only per-trial rollout seeding,
    which is what makes the "≥3 seeds" requirement possible on one split. Driven by the repo
    variable `BENCH_SPLIT_SEED` because `workflow_dispatch` caps inputs at 10 and that list is full.
  - **Agent turns.** SkillOpt runs SpreadsheetBench with up to **30** turns; the adapter default
    is 5, a real handicap on a multi-round benchmark. Full now uses 30; smoke stays at 5 so its
    numbers remain comparable to its own history.
  - **Scope labeling.** `actions: [edit]` is *not* machine-enforced (nothing in `core/` or
    `skills/` reads it); scope comes from `capabilities: [system-prompt]` over a single
    `prompt.md`, which is a closer match to "skill text only" than `skill-package` would be.

### Changed
- **SpreadsheetBench formula recalculation is no longer serialized.** The vendored
  `just_open_libreoffice` lets soffice use its default user profile, so concurrent instances
  conflict and it had to run behind a process-global lock — the full tier's scoring bottleneck at
  912 x 3 = 2,736 serialized soffice startups per evaluation, unaffected by
  `SPREADSHEETBENCH_CONCURRENCY`. `_recalc_workbook` replaces it, giving each invocation its own
  `-env:UserInstallation` profile, capturing output (the vendored helper printed on every failure
  path), leaving the workbook untouched when recalc fails, and reporting failure rather than
  raising. Verified against a fake soffice for profile uniqueness, concurrency, in-place
  replacement, timeout/exit/missing-binary handling and stdout silence.

### Fixed
- **SpreadsheetBench rollouts could segfault the whole run (pandas 3.x + PyArrow strings).**
  `_spreadsheet_preview` builds its preview with `pd.read_excel`; pandas 3.x makes `str`
  columns `ArrowStringArray`, so construction goes through pyarrow's C++ layer. Called
  concurrently from the rollout thread pool that crashed with SIGSEGV in
  `ArrowStringArray._from_sequence` — uncatchable, so one bad preview killed the algorithm
  process and every completed iteration with it (run 30634898569 lost 68 minutes and ~$6
  after an accepted baseline). The adapter now pins `mode.string_storage = "python"` once per
  process, so the crashing frame is never reached; verified on pandas 3.0.5 / pyarrow 25.0.0
  that the preview text is byte-identical to the default, so the agent's prompt — and result
  comparability — are unchanged. Set once at import rather than per call, because
  `pd.option_context` restores a process-global option on exit and would race the other
  rollout threads. Guarded by both runtime tests and dependency-free AST checks, since
  `core[dev]` has no pandas and a skipped guard is no guard.
- **A failed benchmark run was recorded as `"conclusion": "success"`.** The completion gate
  (`Assert the suite run completed`) ran *after* `Write run metadata`, and `job.status` is
  evaluated when a step runs — so a run that crashed mid-optimization and failed the gate still
  wrote `success` into `runmeta.json`, which the aggregate job then published to
  `benchmark-history`. Runs 30553822478 and 30608405812 are both recorded as successes on the
  history page despite failing. The gate now runs before the publishing steps; everything
  downstream is `if: always()`, so metrics/UI/artifacts/PR-comment are still published on
  failure — only the recorded conclusion changes.
- **Command-injection vector in the benchmark job's metadata step.** `github.head_ref` (an
  attacker-controlled PR branch name) was interpolated straight into an inline script on a
  **self-hosted** runner. It now travels via the environment, and both free-form fields
  (`branch`, `source`) are emitted as JSON string literals — shell quoting alone let a branch
  name containing a double quote produce an unparseable `runmeta.json`. Verified against 24
  combinations of hostile branch name x event x job status. `benchmarks.yml` is now
  actionlint-clean.

- **SpreadsheetBench formula recalculation was silently never running (#256).** #240 widened the
  *directories* the adapter creates so the uid-1000 container could write its output; the output
  *file* it writes is still owned by uid 1000 at ~0644, so the host-side scorer could not rewrite
  it. `just_open_libreoffice` recalculates into a `/tmp` tempdir and moves the result back —
  cross-filesystem, so `shutil.move` falls back to `copy2`, which opens the container-owned file
  for writing and dies with `[Errno 13] Permission denied: <n>_<id>_output.xlsx`. The adapter
  swallowed that with `except Exception: pass`, so comparisons ran on **stale cached values** and
  formula-only cells read as empty — every score a floor, and the noise looked like model variance
  (baseline 0.293 vs 0.393 on two runs of the same 10 tasks). `chmod` cannot fix this (you may not
  chmod a file you do not own), so `_reclaim_container_file` replaces the file with a byte-identical
  copy we own — the create and rename need write+execute on the *directory*, which is already
  `0o777` and deliberately non-sticky for per-rollout dirs. A recalc that still fails is now
  reported as an `INFRASTRUCTURE:` line in the task feedback instead of being swallowed, so the
  optimizer is told not to spend budget on it.
- **A native crash in a phase process left no evidence (#257).** Run 30608405812's algorithm step
  died with `{"returncode": -11, "signal": "SIGSEGV"}` and nothing usable: a segfault has no Python
  traceback, and `_step_failure` captured only `stderr[-8000:]` — a window filled entirely with
  routine per-rollout scoring chatter emitted long after the crash-relevant output. Now:
  `cap_evolve` enables `faulthandler` on import (stderr only, so the stdout JSON contract is
  untouched; opt out with `CAPEVOLVE_NO_FAULTHANDLER=1`), the captured stderr keeps a head *and* a
  tail with an explicit omission marker, and the signal hint is signal-specific — SIGSEGV no longer
  misdirects the reader to the OOM killer and `dmesg`.
- **A printing scorer no longer destroys a completed run (`cap-evolve run` stdout contract).**
  `harness.evaluate_candidate` now wraps the whole run+score body in
  `redirect_stdout(sys.stderr)`, not just the rollout pool. Only the RUN phase was guarded
  (`run_trials_pool`, for tau2's progress output); SCORING was free to print, and
  SpreadsheetBench's vendored comparator prints `"Cell values in the specified range are
  identical."` on every *passing* check (its LibreOffice recalc helper prints on every
  failure path). That prose landed on the baseline phase's stdout, so `cap-evolve run`'s
  `json.loads(proc.stdout)` died with `Expecting value: line 1 column 1` — *after* an
  11-minute, $2.65 baseline had already succeeded and been written to disk, and before any
  optimization iteration ran ([run 30553822478](https://github.com/skillberry-ai/cap-evolve/actions/runs/30553822478)).
  The bug was latent until spreadsheetbench first scored above zero: no passing comparison,
  no print. As a second line of defense, `cli._json_payload` now extracts a phase's JSON
  payload from stdout newest-object-first instead of assuming the buffer is pure JSON, so
  one stray `print` anywhere under an adapter can no longer discard finished work — while
  stdout carrying no JSON at all still fails loudly.
- **Benchmark CI robustness (skillberry-1 self-hosted runner).** Three fixes so a broken
  runner or gateway is *loud*, not a silent all-0.000 "success": (1) `ci_setup.sh` now
  installs + hard-verifies the `claude-code` optimizer CLI — when it was missing the
  optimizer failed every iteration (`cli_present:false`) and every task reported
  `best=seed`/0.000; (2) `ci_setup.sh` adds a **model-gateway budget preflight** — one
  tiny gpt-oss call that aborts with a clear error on `429 budget_exceeded` (the shared
  LiteLLM gateway hitting its spend cap 429s both the agent and the optimizer, killing
  every rollout with `INFRASTRUCTURE_ERROR`); (3) `run_suite.sh` iterates the task list on
  FD 3 (+ `run_task </dev/null`) so the optimizer subprocess reading stdin can no longer
  DRAIN the here-string and cut the suite off after one task. `metrics.py` now detects an
  infra-dominated eval (majority trials errored + reward≈0) and renders it as
  `⚠️ infra-error`, excluding it from the suite mean/flip counts so a gateway outage no
  longer looks like a capability regression.

### Added
- **SWE-bench oracle mode + calibrated smoke selection.** The SWE-bench adapter gains
  `SWEBENCH_ORACLE=1`, which attaches the "Oracle" retrieval context (the file[s] the
  gold patch touches, from `princeton-nlp/SWE-bench_Lite_oracle`'s `text` field) to the
  prompt so a single-shot mid-tier reader (gpt-oss-120b) can produce a diff that actually
  applies — blind problem-statement-only prompting is near-hopeless for weaker readers.
  Scoring still runs on the base dataset (eval path unchanged); off by default. Adds
  `<patch>…</patch>` extraction for the oracle output contract. New offline dev tool
  `ci/benchmarks/swebench/utils/select_candidates.py` builds a candidate pool (Verified∩Lite,
  Easy `<15 min` difficulty, single-file/small-patch, oracle-context under a token budget)
  used to pick the swebench smoke tier's 5 tasks (`ci/benchmarks/swebench/smoke/tasks.json`),
  which now run through the same `run_suite.sh` path (baseline + optimized in one run) as
  every other benchmark's smoke tier. `select_candidates.py` and its output
  (`utils/smoke_candidates.json`) live under `utils/` — not read by CI, only for
  re-picking tasks later.
- **SkillsBench smoke tier aligned with tau2/swebench.** `ci/benchmarks/skillsbench/smoke/tasks.json`
  grows from 2 tasks (tag `hard`) to all 10 tasks the adapter's `TASK_IDS` allowlist
  supports (tag `repr`, matching tau2's count and the tau2/swebench tag convention) —
  the same pool already used and baselined in `docs/REPRODUCE_skillsbench.md` (baseline
  pass rate 0.333, not 0). `ci/benchmarks/README.md`'s "Hard-only suite" framing is
  reworded to "Calibrated-headroom suite" to match this and swebench's own
  `select_candidates.py` selection goal (nonzero but not saturated at baseline), rather
  than the stricter "every curated task has baseline reward 0" claim neither benchmark
  actually satisfies.
- **Adapter-native batch scoring (`score_batch`).** New optional adapter hook,
  `score_batch(tasks, rollouts) -> {task_id: Score}` — the scoring-side counterpart to
  `run_batch`/`run_trials` (see `docs/ADAPTER_CONTRACT.md`). The harness calls it once
  per trial instead of looping `score()` per task; any task id it omits falls back to a
  single `score()` call, so a partial implementation can never silently drop a score.
  The SWE-bench adapter now implements it, batching a trial's instances into **one**
  `swebench.harness.run_evaluation` call with a comma-separated `--instance_ids` list —
  previously every trial ran one Docker-harness subprocess per instance with nothing for
  `--max_workers` to parallelize over, so `SWEBENCH_MAX_WORKERS=10` (already set in CI)
  was a no-op. Adapters that don't implement `score_batch` are unaffected.
- **Consuming-LLM profiles.** Declare the runtime/consuming model via `target_model`
  (a concrete model id or a capability tier: `frontier|strong|mid|weak`) in
  `capevolve.yaml`. The optimizer prompt (new `{{TARGET_READER}}` block) and the
  capability guidance now adapt their proposed edits to that reader — a weaker reader
  gets more explicit rules, worked examples, literal slot-filling docs, and code
  enforcement; a frontier reader gets leaner prose that explains the *why*. This is
  DISTINCT from `optimizer_model` (which proposes the edits). `cap-evolve check` warns
  (non-blocking) when the declared consuming model's tier differs from the runner's
  actual model (via an optional `adapter.runner_model()` hook). Report + dashboard
  surface the consuming model alongside the optimizer model. Blank `target_model`
  preserves prior behavior exactly; optional `target_profile_file` overrides a tier's
  built-in brief. The tau2-airline example opts in (`gpt-oss-120b`, tier `mid`).
- **`cap-evolve run --resume`** — continue an interrupted run (pod eviction, crash,
  timeout) from its last completed state instead of starting over. Reopens the run dir
  (`--run-ts`, else the latest under the base) via `RunDir.create(exist_ok=True)` so it
  no longer fails with `FileExistsError`; skips the baseline when it already ran; picks
  the loop up at iteration N+1 from the current best (spend, journal, git history, and
  the test seal are all preserved); and skips a re-finalize when the test seal is already
  burned. Explicit budget flags (`--max-iterations`, …) **extend** a resumed run. Works
  across every algorithm — `hill-climb`/`skillopt` already resumed from rollouts, and
  **`gepa` now reconstructs its full pool/lineage/frontier** from the run dir (a tiny
  `gepa_state.json` checkpoint + rollouts) so its Pareto search continues where it stopped.
- **Six more coding agents as optimizers** — `cursor` (Cursor `cursor-agent`),
  `droid` (Factory Droid), `copilot` (GitHub Copilot CLI), `kimi` (Moonshot Kimi),
  `pi` (earendil-works Pi), and `antigravity` (Google `agy`, a configurable wrapper).
  This brings cap-evolve's supported coding-agent set to parity with
  [obra/superpowers](https://github.com/obra/superpowers). Each is **one row** in
  `skills/optimizers/registry.yaml` (verified headless command, except `antigravity`
  which reads `CAPEVOLVE_ANTIGRAVITY_CMD` because its auth is Google-Sign-In-only and
  its non-interactive approve flag is unconfirmed) plus a per-CLI
  `run-optimizer/references/<name>.md`. `install.sh --host` learns each one's skills
  dir. No core/runner changes — the registry-driven `run-optimizer` already generalizes.
- **Per-iteration optimizer dollar cap** (`optimizer_usd_per_iter` in `capevolve.yaml`):
  threaded through `run-optimizer --usd-budget` into a new registry `usd_budget_flag`,
  enforced natively by the optimizer CLI where supported (claude-code →
  `--max-budget-usd N`). Optimizers without a native $ cap (e.g. ibm-bob) ignore it and
  are bounded by `optimizer_max_turns` / the cumulative `max_optimizer_usd`.
- intake `INPUTS.md` now covers the **runner model + credentials + custom
  OpenAI-compatible/RITS endpoint** and **obtaining/installing a benchmark repo** (with
  the resolved commit recorded), aligning the interview contract with the README.
### Fixed
- Scaffolded project adapter template (`templates/project/adapters/adapter.py`) matched
  the real `CapabilityAdapter` contract: abstract `tasks` / `run_target(task, ctx, *, seed)`
  / `score`, with `materialize`/`live`/`apply`/`run_batch` documented as optional
  overrides. The old stub used a stale `run_target(task, candidate_dir, split)` signature
  and presented `apply` as a 4th abstract method, which a filled-in body could make the
  stub-probe silently pass.
- Honest-eval core (`cap_evolve`): seeded splits with a sealed test set,
  significance gate, multi-trial variance, pass^k + pass@k, bootstrap CIs.
- **19 Agent Skills**: phases (intake, implement-and-check, baseline, evaluate,
  diagnose, gate, finalize, report), capabilities (system-prompt, tools, mcp-tool,
  skill-package), algorithms (**hill-climb** with `--focus all|cyclic|hardest-first`,
  **gepa**, **skillopt**), one **run-optimizer** skill backed by
  `optimizers/registry.yaml` (claude-code, codex, gemini-cli, opencode, openclaw,
  ibm-bob, generic, mock), and orchestrate + a `using-cap-evolve` session-start router.
- **`gepa`** (flagship): real GEPA — two-stage minibatch-then-full-val economy,
  per-instance Pareto frontier with frequency-weighted parent sampling, trace-based
  reflective dataset, round-robin component focus, system-aware merge across lineages,
  rollout/metric-call budget, eval cache (arXiv:2507.19457).
- **`skillopt`** (flagship): epochs × mini-batches with a textual learning rate
  (integer edit budget on a constant|linear|cosine schedule), within-epoch
  rejected-edit buffer, and a gated epoch-boundary slow/meta update (arXiv:2605.23904).
- Git-backed iteration store (default) + optimizer memory (MEMORY.md/STATE.md/rejected.jsonl).
- **Self-contained** `dashboard.html` (no CDN): KPI strip, cumulative-best stair,
  tasks×iterations pass/fail heatmap, per-iteration diff, lineage tree (merges as
  multi-parent), optimizer-vs-runner cost/tokens/latency, annotations — plus a
  `cap-evolve report --terminal` ANSI report for in-chat progress.
- **Claude Code plugin** (`plugins/cap-evolve/`, install `claude --plugin-dir
  ./plugins/cap-evolve`): every skill as `/cap-evolve:<skill>` (dual-mode: standalone
  slash command + orchestrator-callable + headless JSON), honesty **hooks** (PreToolUse
  denies edits to the sealed test/gold; Stop/SubagentStop block until `cap-evolve check`/
  the gate is green) in **core-owned scripts**, read-only diagnoser + writer proposer
  subagents, and the `using-cap-evolve` router.
- Host-agnostic installer.
- Examples: toy_calc, json_extract, date_tool, skills_bench, tau2_airline
  (real run: 0.46 → 0.80 on 50 tasks).
- `--resume` to continue a run from its current best.

### Changed
- **Skill library collapsed (26 → 19).** The 8 per-CLI optimizer skills became one
  `run-optimizer` skill + a one-row-per-optimizer `optimizers/registry.yaml`; the
  three hill-climb algorithm clones (all-at-once / cyclic / hardest-first) became one
  `hill-climb` skill with `--focus`. Adding an optimizer is now one YAML row.
- **Adapter contract changed** to `tasks(split)` · `run_target(task, ctx, *, seed)` ·
  `score(task, rollout)` · pure `materialize(candidate_dir, edits)` + a `live(candidate_dir)`
  context manager. `apply()` is retained as a back-compat hook. A per-trial `seed` is
  threaded into `run_target`, so pass^k measures real variance.
- **Honest-eval upgrades:** the **paired** significance gate is the default (the engine
  auto-selects it because candidate & current share the val tasks); test seal is now
  **seal-on-success** (a finalize crash no longer burns the headline); infra-vs-capability
  failures use a structured `Rollout.error` signal instead of substring-matching feedback.

### Notes
- Skill names are hyphenated to comply with the Agent Skills `[a-z0-9-]` rule.
