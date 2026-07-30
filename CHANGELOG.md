# Changelog

All notable changes to cap-evolve are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

## [Unreleased]
### Changed
- **BREAKING (gate semantics): `k_se` is now a z *quantile* in `gate_mode: paired`, not
  the multiplier.** SE(Δ) is estimated from the same n val deltas, so the standardized
  mean difference is t-distributed with df = n−1, not normal. The gate now converts
  `k_se` to its one-sided normal tail α = P(Z > `k_se`) and uses the bar
  `t_{1−α, n−1} · SE`. `t ≥ z` is a theorem for every finite df, so **the gate can only
  get stricter** — but it is strictly stricter, so **candidates that were accepted near
  the old bar can now be rejected**, and re-running a prior optimization may take a
  different path. The widening depends on `k_se` *and* n: at `k_se 1.0` the bar is
  1.32× wider at n=3, 1.06× at n=10, 1.02× at n=30; at `k_se 3.0` it is 6.4× at n=3.
  `gate_mode: significant` is unchanged (`k_se` is still the multiplier there). `k_se`
  above 26.5 now raises (its normal tail underflows float64 for some df); use ≤ 3. Documented in
  `docs/HONEST_EVAL.md` guarantee 3, `templates/project/capevolve.yaml`, and
  `docs/OPTIMIZE_YOUR_OWN.md`. The one committed run artifact with real gate decisions
  (`examples/skillsbench/run_full`, n=7, `k_se 0.2`) re-decides **identically** — zero
  flips — and `docs/RESULTS.md`'s τ² runs (n=30, `k_se 0.3`) are far from any margin, so
  published results still reproduce.
- **BREAKING (adapters with < 6 tasks): a val split of 0 or 1 task is now refused.** Any
  adapter whose task list yields `val < 2` under its ratios hard-fails at split freeze
  with `TinyValSplitError` instead of silently running a meaningless gate. With the
  default 0.5/0.25/0.25 ratios that means ≥ 6 tasks (≥ 20 for the recommended val ≥ 5);
  with 4–5 tasks set all three ratios to 0.25/0.5/0.25. `CAPEVOLVE_ALLOW_TINY_VAL=1`
  opts out, and permanently brands the run's artifacts as not-an-honest-gate.
  `skillcheck.temp_run_dir`'s default id set grew 4 → 8 for the same reason.

### Fixed
- **Tiny/empty val splits can no longer reach a gate decision, on any path (#113).** The
  guard now runs at split freeze, `baseline`, `reuse_baseline`, and the `--resume`
  fast-path — and, decisively, **inside `gate.decide` itself**, which is the chokepoint
  every mode of every algorithm routes through. This closes three previously unguarded
  production paths (`reuse_baseline` returned before `baseline()`, so a run created under
  the escape hatch became a reusable seed for later runs that were never marked
  dishonest; `--resume` and `--reuse-baseline` returned before any check) and also catches
  a *healthy* split whose realized pair count collapsed because a candidate errored on
  most val tasks (`_paired_deltas` intersects task ids).
- **Escape-hatch runs are now visibly branded instead of looking honest.** A run that set
  `CAPEVOLVE_ALLOW_TINY_VAL=1` writes a `tiny_val_bypass` marker to `state.json`;
  `final.json` gains `honest_gate: false` and a `warnings` array; `report.md` leads with
  `⚠ NOT AN HONEST GATE` and retracts its "held-out tasks the optimizer never saw"
  claim; and the dashboard renders a red banner above every number (`dashboard.py` also
  had no `split_warning` branch at all — it does now). LOW CONFIDENCE gate decisions
  likewise now surface in `report.md`, not only in `events.jsonl`.
- **`stats.t_critical` was silently wrong for α below ~1e-12.** It bisected on
  `1.0 - alpha`, which is exactly `1.0` in float64 below α ≈ 1e-16, so the search
  converged onto a garbage plateau: −5.9% at `k_se=8`, −29% at `k_se=8.3`, constant for
  `k_se` 10…38, and at `k_se ≥ 38.5` α underflowed to 0, the function returned `0.0`, and
  a `max(k_se, ...)` clamp **silently reverted the bar to the uncorrected z** — the exact
  bug the correction exists to fix. It now bisects on a new cancellation-free survival
  function `stats.t_sf`, verifies the solved value reproduces α before returning, and
  raises rather than returning a sentinel. Cross-checked against an independent closed
  form at df=2 to 3e-13 relative error across `k_se` 1…37. The `max()` clamp is gone
  (it bound in 0 of ~30,000 valid cases; its only live effect was hiding this failure).
  `betainc`'s continued fraction now raises on non-convergence instead of returning a
  half-converged value, and `t_critical` raises `ValueError` on invalid α/df instead of
  returning `0.0`/`inf` sentinels that would get multiplied by an SE.
- **`check_val_size`'s remediation option 2 did not work.** It suggested `split_val: 0.4`,
  but the CLI always builds all three ratios, so that yields (0.5, 0.4, 0.25) — still
  `val=1` at n=3 and n=4, i.e. exactly the users hitting the error. It now gives the full
  verified triple (0.25/0.5/0.25, correct for every n ≥ 4), notes that option 3 needs
  `test ≥ 1` too, and states that at exactly 3 tasks no ratio can work.
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
- **Protected-paths tamper guard (honesty).** New `cap_evolve/protect.py` proves the
  optimizer never edited the scorer / eval harness / task data. A SHA-256 manifest of
  the protected paths is recorded at `baseline` (`protected.json`) and re-verified
  inside `evaluate_candidate` — the chokepoint every evaluation (baseline, each
  iteration's val gate, `finalize`) goes through — plus GEPA's minibatch path. Any
  modification, deletion, or newly-added protected file logs a `tamper_detected` event
  (surfaced as a red banner at the top of the dashboard and of `report.md`) and raises
  `TamperError` naming the file, before the candidate can be scored, snapshotted,
  become best, or seal the test split. Verification runs **both before and after** every
  scoring pass — `evaluate_candidate`, GEPA's `_eval_minibatch`, and once more
  immediately before `finalize` burns the seal — so a writer that lands *during* scoring
  (a detached grandchild outliving the optimizer subprocess) invalidates the score
  instead of being recorded. The manifest itself is protected: its digest is logged in
  `events.jsonl`, and a manifest that goes missing, becomes unparseable, or stops
  matching that digest is a hard failure rather than a silent re-record from the current
  (possibly tampered) tree. Bytecode is hashed like any other file — `load_adapter` sets
  `sys.dont_write_bytecode` and clears the adapter's `__pycache__`, closing the PEP 552
  `UNCHECKED_HASH` pyc attack (a planted cache entry ran a hacked `score()` with the
  source's SHA-256 unchanged) without needing a `.pyc` exclusion. A protected file
  replaced by a symlink reads as a change rather than de-protecting itself. Defaults
  derive from the project layout (`adapters/`, `capevolve.yaml`, the spec's
  `dataset_source`/`split_ids_file`, `*gold*` **data** files — prose like
  `docs/golden-rules.md` is no longer swept in); override with `protected_paths` in
  `capevolve.yaml`, where a malformed or empty value is a hard error, never a silent
  fallback to the defaults. The capability dir is never protected — it is the target.
  `--reuse-baseline` inherits the prior run's manifest and refuses a prior run that
  logged a tamper. The `PreToolUse` honesty hook denies writes to protected paths
  (case-folded, for APFS/NTFS) and to the run's own evidence (`protected.json`,
  `events.jsonl`, `state.json`, `best.txt`). Content hash, not mtime (spoofable). Zero
  new deps (`hashlib`). `docs/HONEST_EVAL.md` states the guarantee as **tamper-evident**
  — detection, not prevention — with its residual gaps named.
- **YAML block sequences in `capevolve.yaml`.** The zero-dependency fallback parser
  (used whenever PyYAML is absent, the documented default state) only understood the flow
  form `key: [a, b]`; the idiomatic block form silently parsed as `{}`. Every
  list-valued key was affected — including `protected_paths`, where it meant a declared
  grader quietly fell back to the defaults with no warning.
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
