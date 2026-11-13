# Backup profile: `tau2-airline` — `benchmarks/tau2/template`, `benchmarks/tau2/examples/airline`; CI `tau2`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | tau2 `reward_info.reward`, binary per trial in airline. Success: reward = 1. Group metric: pass^k (`final.json` `pass_k`). Secondary: `db_match`. |
| Infra rule | published: drop. Detectors: termination `INFRASTRUCTURE_ERROR`, `UNEXPECTED_ERROR`, `TIMEOUT`; user-simulator `###STOP###` leak. |
| Telemetry | tokens: sum of `trace[].usage`; latency: `<run>/native_sims/<tag>/<split>/results_*.json` `duration`; steps: count from the trace; termination: `metadata.termination_reason`. |
| Cost | agent: `metadata.cost_source` (`tau2`, `partial_messages`, `unpriced`), `zero_means: unknown` unless tagged `tau2`. User simulator: `metadata.usersim`, list estimate, **already inside `usd`** (report it apart). Optimizer: `step` events; in agent mode it may be null or hand-entered. |
| Splits | template: core ratios. airline: `split_ids.json` 50/50/50 (no holdout), `agentopt_split.json` 26/12/12 (holdout), `smoke_split.json`, `itest_split.json`. |
| Baselines | seed |
| Gold | `vendor/tau2-bench/data/tau2/domains/airline/tasks.json` (`evaluation_criteria`), `src/tau2/evaluator/`. In records: `metadata.tau2_reward_info.action_checks`, which is copied into `work/*/trajectories/`. Allowed: train/val. Forbidden: test ids. |
| Isolation | none |
| Agent evidence | the candidate's `tools.py` runs in-process. |
| Models as used | `native_sims` `info.agent_info.llm`, `info.user_info.llm`. |
| External state | `native_sims/`, `vendor/tau2-bench*`. |
| Sources | committed exports `run_full/`, `run_agentopt*/` (some made on another host); `erezh/_campaign/` on Box (duplicate check); git `research/capevolve-paper-*` branches. |
| Reproduce | launch: `setup.sh`, `run.sh`, `capevolve*.yaml`, split files; clone: tau2-bench at the recorded SHA (unpinned `main`; check `TAU2_COMMIT.txt` against `demo.cast`); unpinnable: gateway backends. |
| Licence | not recorded |
| Secrets | `native_sims/**` `llm_args`; `OPENAI_API_KEY` in `.env`. |
