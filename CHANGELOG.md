# Changelog

All notable changes to cap-evolve are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

## [Unreleased]
### Added
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
