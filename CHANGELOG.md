# Changelog

All notable changes to cap-evolve are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

## [Unreleased]
### Fixed
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
