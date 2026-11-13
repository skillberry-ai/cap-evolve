# Backup profile: `tau2-sierra-airline` — `benchmarks/tau2/examples/sierra_airline/{direct,blackbox}`; CI `tau2_sierra`, `tau2_sierra_blackbox`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

tau2 airline on pinned vanilla tau2, with a direct arm and a blackbox delivery arm (Skillberry store + SPA).

| Key | Value |
|---|---|
| Bench names | `tau2_sierra`, `tau2_sierra_blackbox`, `tau2_blackbox`, run-dir names `sierra`, `direct`, `blackbox`; settings: `direct`, `blackbox` |
| Code | `benchmarks/tau2/examples/sierra_airline/{direct,blackbox}/` (`adapters/adapter.py`, `direct/adapters/tau2_tailoring.py`, `capevolve.yaml`, split files, `optimizer/INSTRUCTIONS.md`, `PROJECT.md`, `setup.sh`, `run.sh`), `benchmarks/tau2/examples/sierra_airline/PROMPT.md`; `skills/interventions/llm-proxies/blackbox/` (`scripts/blackbox_env.py`); CI `ci/benchmarks/tau2_sierra/{smoke,full,integration}/`, `ci/benchmarks/tau2_sierra_blackbox/`; `tau2_blackbox` at `8860d243a^:ci/benchmarks/tau2_blackbox` |
| Reward | as `tau2-airline`; direct adds `raw.db_match` |
| Infra rule | as `tau2-airline` |
| Telemetry | `tokens` not set (`not_recorded`); trace = `sim.model_dump()`: `duration`, `termination_reason`, `messages[].usage`, `agent_cost`, `user_cost` |
| Cost | agent: not measured (`zero_means: unknown`); litellm has no price for the agent model; blackbox: SPA reports no usage; user simulator: `trace.user_cost` (0 when unpriced: unknown); optimizer: as `_core.md` |
| Splits | `split_ids_budget.json`: 7 = 7 = 7 (`[8,10,20,23,35,42,44]`, no holdout); `split_ids.json` 50×3; `split_ids_smoke.json` (`["9"]`); `final.json` `train_equals_val` |
| Baselines | seed |
| Capability | direct: tools (`tools.py`); blackbox: the store skill `my_skill` + `primitive_tools/` (protected: `primitive_tools/*`, `my_skill/SKILL.md`, `reference/*`) |
| Gold | allowed by design: `runner_repo_path: ../../vendor/tau2-bench` (task definitions, reward checks) and gold actions in `trajectories/` (`direct/optimizer/INSTRUCTIONS.md`). Check for hardcoded task ids or gold values (VERIFICATION_SCAN A1b). Forbidden: nothing beyond the declared split, since train = test |
| Isolation | none |
| Agent evidence | direct: in-process tools; blackbox: SPA on port 7000 + the tau2 `EnvironmentManager` on port 8004: grep `/tmp/skillberry-agent.log`, `/tmp/tools-agent.log` |
| Models as used | native results `info.agent_info.llm`, `info.user_info.llm` (the spec says agent `aws/claude-haiku-4-5`; `PROJECT.md` says `aws/claude-sonnet-5`; optimizer `claude-opus-5-5` in the yaml vs `claude-opus-4-8` in `PROJECT.md`/`PROMPT.md`) |
| External state | `.capevolve/` (direct), `.capevolve-blackbox/` (blackbox); `native_sims/`; `vendor/tau2-bench`, `vendor/tau2-bench.COMMIT`, `vendor/skillberry-store`, `vendor/skillberry-agent` and their venvs; the store DB; **volatile:** `/tmp/env_manager.log`, `/tmp/skillberry-agent.log`, `/tmp/skillberry-store.log`, `/tmp/tools-agent.log`, `/tmp/tools-store.log`, `/tmp/skillberry-*-service.pid`; CI: `${CAPEVOLVE_CI_CACHE}/spa-vendor` |
| Sources | committed `benchmarks/tau2/examples/sierra_airline/{direct,blackbox}/run/` (`final.json` + `ui/`); `benchmark-history` `*tau2_sierra*`, `*tau2_blackbox*` runs and records (branch `tau2_vanilla_blackbox`); docs `docs/REPRODUCE_tau2_sierra_direct_blackbox.md`, `docs/BLACKBOX.md`, `docs/RESULTS.md`; ledgers: as `_core.md` |
| Reproduce | tau2 at `TAU2_REFERENCE_SHA` (`4ce7c0397c1e…`, tau2 1.0.1, clean-checkout check in `setup.sh`); store `aviweit/skillberry-store@c39d472`; SPA `skillberry-ai/skillberry-agent@e359494`; services: env manager, store, SPA (`blackbox/run.sh`); extra `websockets>=13.0`; unpinnable: gateway backends |
| Licence | unverified: tau2-bench and Skillberry licences are not recorded in the repo — read them from the clones |
| Secrets | `llm_args` in native results (the adapters leave `api_key` out); `.env` |
