# Backup profile: `skillsbench` — `benchmarks/skillsbench/{template,examples/shared_skills}`; CI `skillsbench`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | verifier `reward.txt`, `result*.json` or CTRF all-pass: binary. Success: all verifier tests pass. Group metric: pass^k. |
| Infra rule | published: drop. Detectors: no reward found, launch failure, timeout. |
| Telemetry | `cost_usd = 0` and `tokens = 0` are hard-coded (`not_recorded`). Latency, steps, termination: BenchFlow `result.json` under the jobs dir, if present. |
| Cost | agent (Claude Code in a container): not metered (`zero_means: unknown`). Optimizer: `step` events. |
| Splits | example: train = val = 7 tasks, test 3. smoke 1/1/1. |
| Baselines | seed |
| Gold | `vendor/skillsbench/tasks/<id>/{tests,solution}`, `.bench_cwd` dataset clone. Allowed: train-task verifiers (`runner_repo_path`). Forbidden: the 3 test tasks' tests and solutions. |
| Isolation | none |
| Agent evidence | `--sandbox docker`. |
| Models as used | the bench command (`--model`) and the agent trajectories. |
| External state | `<run>/bench_jobs/`, `.bench_cwd`, `vendor/skillsbench`, Docker images. |
| Sources | git `skillsbench-history`, `skillberry-runs/skillsbench`; CI records. |
| Reproduce | clone at the recorded SHA (`SKILLSBENCH_COMMIT.txt`), but tasks run from BenchFlow's own `--source-ref main` cache: record its SHA. `benchflow` version. |
| Licence | the four seed skills are Anthropic-licensed, not for redistribution (not to be published). |
| Secrets | `--agent-env ANTHROPIC_AUTH_TOKEN=…` on the command line, in logs and job configs; `.env`. |
