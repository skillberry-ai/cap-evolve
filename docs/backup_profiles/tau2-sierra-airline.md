# Backup profile: `tau2-sierra-airline` — `benchmarks/tau2/examples/sierra_airline/{direct,blackbox}`; CI `tau2_sierra`, `tau2_sierra_blackbox`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | as `tau2-airline`. |
| Infra rule | as `tau2-airline`. |
| Telemetry | no `tokens`. Trace = `sim.model_dump()` (`duration`, `termination_reason`, `messages[].usage`). |
| Cost | agent not measured (`zero_means: unknown`); SPA reports no usage. User simulator: `sim.user_cost`. |
| Splits | `split_ids_budget.json`: 7 = 7 = 7 (no holdout); `split_ids.json`; `split_ids_smoke.json`. |
| Baselines | seed |
| Gold | **allowed by design:** `runner_repo_path: ../../vendor/tau2-bench`, and gold actions in `trajectories/`. Check for hardcoded task ids or values (VERIFICATION_SCAN A1b). |
| Isolation | none |
| Agent evidence | direct: in-process tools; blackbox: SPA (port 7000) + env manager (port 8004). |
| Models as used | native results `info.*.llm` (the spec, PROJECT.md and REPRODUCE disagree). |
| External state | `.capevolve/`, `.capevolve-blackbox/`, `vendor/{tau2-bench,skillberry-store,skillberry-agent}` and their venvs, the store DB, `/tmp/skillberry-*.log`, `/tmp/env_manager.log`, `/tmp/tools-*.log` (**volatile**). |
| Reproduce | tau2 @ `TAU2_REFERENCE_SHA`; store `aviweit/skillberry-store@c39d472`; SPA `skillberry-ai/skillberry-agent@e359494`. |
| Licence | not recorded |
| Secrets | `llm_args`; `.env`. |
