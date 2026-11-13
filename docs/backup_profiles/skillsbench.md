# Backup profile: `skillsbench` — `benchmarks/skillsbench/{template,examples/shared_skills}`; CI `skillsbench`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

SkillsBench tasks run by BenchFlow (`bench eval run`), with Claude Code as the agent, in Docker.

| Key | Value |
|---|---|
| Bench names | `skillsbench`; experiments `runnable-subset-43`, `task-by-task-43`, `task-by-task-87` (a sweep: one unit per task); settings: none, or the experiment name |
| Code | `benchmarks/skillsbench/template/` (`adapter.py`, `capevolve.yaml`); `benchmarks/skillsbench/examples/shared_skills/` (`adapters/adapter.py`, `capevolve*.yaml`, `split_ids.json`, `smoke_split.json`, `setup.sh`, `run.sh`, `smoke.sh`, `optimizer/INSTRUCTIONS.md`, `seed_capability/`); CI `ci/benchmarks/skillsbench/{smoke,full}/` |
| Reward | verifier `reward.txt`, else `result*.json`/`*scored*.json`, else CTRF all-pass: binary (`adapters/adapter.py`). Success: every verifier test passes. Group metric: pass^k; CTRF per-test pass counts as a secondary partial metric |
| Infra rule | published: drop. Detectors: no reward found, launch failure, timeout (`SKILLSBENCH_TASK_TIMEOUT × waves + 600`) |
| Telemetry | `tokens` = 0 and `cost_usd` = 0.0 are hard-coded (`not_recorded`); latency, steps, termination: BenchFlow `result.json` and verifier logs under the jobs dir (`unverified`: field names not yet seen on a real run) |
| Cost | agent (Claude Code in the container): not metered, `zero_means: unknown`; optimizer: `step` events `opt_cost_usd`, `opt_tokens` |
| Splits | example: train = val = 7 tasks, test 3 (`pdf-excel-diff`, `pptx-reference-formatting`, `reserves-at-risk-calc`); smoke 1/1/1; template: core default |
| Baselines | seed |
| Capability | shared Agent Skills (skill packages), passed to the agent with `--skill-mode with-skill --skills-dir` |
| Gold | `vendor/skillsbench/tasks/<id>/` verifier tests and oracle solution (`unverified`: exact names `tests/`, `solution/solve.sh`); BenchFlow's dataset clone under `.bench_cwd`. Allowed: train-task verifiers (`runner_repo_path: ../../vendor/skillsbench`). Forbidden: the 3 test tasks' tests and solutions. The seed `pdf` skill comes from `pdf-excel-diff/environment/skills/pdf`: environment material, not gold |
| Isolation | none |
| Agent evidence | `--sandbox docker`; check whether the container mounts tests or solutions (`unverified`) |
| Models as used | the bench command line (`--agent claude --model …`) and the agent trajectories (`*trajectory*.jsonl`) |
| External state | `<run>/bench_jobs/<cand>/seed<k>/<ts>/<task>__<hash>/` (fallback `.capevolve/.bench_runs/default`); `$SKILLSBENCH_BENCH_CWD` (default `<repo>/.bench_cwd`, about 1.1 GB, including `skillsbench_skills_*` temp dirs); `vendor/skillsbench/`; `~/.local/bin/bench` and its uv tool env; Docker images and containers per task; the agent's trajectories `*trajectory*.jsonl` and BenchFlow `result.json` inside each task dir of `bench_jobs/` |
| Sources | committed `benchmarks/skillsbench/examples/shared_skills/run_full/` (`events.jsonl`, `baseline.json`, `final.json`, `history.jsonl`, `rejected.jsonl`, `JOURNAL.md`, `report.md`, `SKILLSBENCH_COMMIT.txt`); git `skillberry-runs/skillsbench` (= `skillsbench-history`: `results/`, `artifacts/`, `recipes/`, `evidence/`, `insights/`, `handoffs/`, `reports/`); `benchmark-history` `*skillsbench*` runs and records; hosts: the CCC podman environment named in the records (`may_exist_at`); docs `docs/REPRODUCE_skillsbench.md`; ledgers: as `_core.md` |
| Reproduce | clone at `SKILLSBENCH_COMMIT.txt`, **and** the SHA of BenchFlow's own `--source-ref main` cache (the tasks that actually ran); `benchflow` version; Docker image digests; launch: `setup.sh`, `run.sh`, `capevolve.yaml`; unpinnable: the agent's model endpoint |
| Licence | the four seed skills are Anthropic-licensed, not for redistribution (`seed_capability/README.md`): do not publish; SkillsBench tasks: `unverified` — read from the clone |
| Secrets | `--agent-env ANTHROPIC_AUTH_TOKEN=…` on the bench command line, so in logs, process records and possibly job configs; `.env` (copied from `~/.claude/settings.json`) |
