# Backup profile: `tau2-airline` — `benchmarks/tau2/template`, `benchmarks/tau2/examples/airline`; CI `tau2`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

tau2-bench airline, run through tau2's own runner with a user simulator.

| Key | Value |
|---|---|
| Bench names | `tau2`; settings: none, or the config variant (`agentopt`, `agentopt-v2`…`v4`, `smoke`, `itest`) |
| Code | `benchmarks/tau2/template/` (`adapter.py`, `capevolve.yaml`); `benchmarks/tau2/examples/airline/` (`adapters/adapter.py`, `adapters/gateway.py`, `capevolve*.yaml`, `*split*.json`, `setup.sh`, `run.sh`, `smoke.sh`, `itest.sh`, `export_run_artifacts.sh`, `PROMPT.md`, `DEMO.md`); CI `ci/benchmarks/tau2/{smoke,full,integration}/` |
| Reward | tau2 `reward_info.reward`, binary per trial in airline (DB × COMMUNICATE). Success: reward = 1. Group metric: pass^k (`final.json` `pass_k`). Secondary: `db_match`. Published metric: `runmeta.reward_metric` |
| Infra rule | published: drop. Detectors: `metadata.termination_reason` in `INFRASTRUCTURE_ERROR`, `UNEXPECTED_ERROR`, `TIMEOUT`; user-simulator `###STOP###` leak; `metadata.error_kind` |
| Telemetry | tokens: sum of `trace[].usage` (prompt and completion per message); latency: `<run>/native_sims/<tag>/<split>/results_<ts>_<pid>.json` `simulations[].duration`; steps: count of agent turns in the trace; termination: `metadata.termination_reason` |
| Cost | agent: `Rollout.cost_usd` with `metadata.cost_source` (`tau2`, `partial_messages`, `unpriced`), `zero_means: unknown` unless `tau2`; `adapters/gateway.py` prices only `aws/gpt-oss-120b`; user simulator: `metadata.usersim{model,prompt_tokens,completion_tokens}`, list estimate inside `usd` (report apart); optimizer: `step` events, null or hand-entered in agent mode |
| Splits | template: core default; airline `split_ids.json` 50/50/50 (no holdout), `agentopt_split.json` 26/12/12 (holdout), `smoke_split.json` 2/2/2, `itest_split.json` 1/1/1 |
| Baselines | seed |
| Capability | system-prompt policy + tools (`seed_capability/`) |
| Gold | `vendor/tau2-bench/data/tau2/domains/airline/tasks.json` (`evaluation_criteria`: gold actions, `communicate_info`, `nl_assertions`), `split_tasks.json`, `src/tau2/evaluator/`; in records: `metadata.tau2_reward_info.action_checks`, copied into `<run>/work/*/trajectories/`. Allowed: train/val. Forbidden: test ids |
| Isolation | none |
| Agent evidence | the candidate's `tools.py` runs in-process: grep trajectories and the tools code for file access |
| Models as used | `native_sims` results `info.agent_info.llm`, `info.user_info.llm`; env `TAU2_AGENT_MODEL`, `TAU2_USER_MODEL` |
| External state | `<run>/native_sims/<tag>/<split>/results_*.json`, `<run>/native_sims/<tag>/started_env_ids_*.txt`; `vendor/tau2-bench/` and `vendor/tau2-bench.COMMIT`; the example's `.capevolve/` project |
| Sources | committed exports `benchmarks/tau2/examples/airline/run_full/` (`TAU2_COMMIT.txt`, `final.json`, `PATCHES.md`, `demo.cast`, `ui/`) and `benchmarks/tau2/examples/airline/run_agentopt{,_v2,_v3,_v4}/` (made on another host: `may_exist_at` the owner's machine); Box old root `erezh/_campaign/` (`INDEX.md`, `runs/`, `final_eval/`, `other/`) and `osher.elhadad/overnight-backup/` for the duplicate check; git `research/capevolve-paper-20261011` (`research/capevolve-paper/experiments/final/manifests/`, `analysis/out/`) and `archive/20261104/*` branches; `benchmark-history` `*-tau2` runs and records; docs `docs/REPRODUCE_tau2.md`, `docs/TAU2_SUMMARY.md`, `docs/RESULTS.md`; ledgers: the ETE gateway (as `_core.md`) |
| Reproduce | launch: `setup.sh`, `run.sh`, `capevolve*.yaml`, split files; data: `vendor/tau2-bench/data/tau2/domains/airline/`; clone: tau2-bench at the recorded SHA (cloned from `main`, unpinned; `run_full` has two SHAs, `TAU2_COMMIT.txt` vs `demo.cast`: both recorded); env: the tau2 venv freeze; unpinnable: gateway backends; smoke: `smoke.sh` |
| Licence | unverified: tau2-bench's licence is not recorded in the repo — read it from the clone |
| Secrets | `native_sims/**` `llm_args`; `OPENAI_API_KEY`, `OPENAI_BASE_URL` in `.env` |
