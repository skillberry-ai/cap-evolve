# Backup profile: `swebench-verified-harbor` — `benchmarks/generic/harbor/template` + `capevolve_harbor/`; CI `swebench`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

Any Harbor dataset, run through Harbor with Claude Code as the agent; CI `swebench` runs SWE-bench Verified this way. For another Harbor dataset, use id `harbor-<dataset>` with these values.

| Key | Value |
|---|---|
| Bench names | `swebench` (CI), `swebench-verified` (runs `200`–`202__full-swebench-verified`, replicate `s<k>` from `/private/tmp/ce-runs/s<k>/`); other Harbor datasets: `harbor-<dataset>`; settings: `registry` or `packaged` mode |
| Code | `benchmarks/generic/harbor/template/` (`adapter.py`, `capevolve.yaml`, `seed_capability/`); `capevolve_harbor/` (`run.py`, `results.py`, `tasks.py`); CI `ci/benchmarks/swebench/{smoke,pilot,full}/` (`overrides.env` with `SWEBENCH_ADAPTER=harbor`, `split_ids.json`), `ci/benchmarks/swebench/utils/` |
| Reward | verifier `reward.json["reward"]`, else `reward.txt` (`capevolve_harbor/results.py`); resolved 1/0 for SWE-bench, possibly partial for other datasets. Success: reward ≥ 1. Group metric: repo, from the instance-id prefix |
| Infra rule | published: drop. Detector: `exception_info` with no reward (a trial with a reward and an exception, for example an agent timeout, counts as measured) |
| Telemetry | trial `result.json` `stats`: `n_input`, `n_output`, `n_cache` tokens separately (summed into one `Rollout.tokens`); latency: per `harbor run` only (`elapsed_seconds`); steps: `agent/trajectory.json`; termination: `exception_info` |
| Cost | agent: `result.json` `stats.cost_usd` (`reported`; `unverified` whether it is Claude Code's own `total_cost_usd`) |
| Splits | CI full: 250 tasks, 100/50/100 (`split_ids.json`); pilot (50) and smoke (5): no split (fit); template: core default |
| Baselines | seed |
| Capability | skill package. Registry mode delivers only the first non-empty of `prompt.md`, `SKILL.md` (`adapter.py`): record the capability as delivered |
| Gold | task `tests/test.sh` (FAIL_TO_PASS harness) and `solution/solve.sh` (gold patch) in Harbor's task cache (`unverified`: path not documented, check `~/.cache/harbor` and Harbor's config); trial `verifier/test-stdout.txt`. Allowed: none. Forbidden: these |
| Isolation | none; the task container's network is public in packaged mode (`capevolve_harbor/tasks.py`) |
| Agent evidence | packaged mode runs `/capability/score.sh` or `score.py` from the candidate: check that the grader was not supplied by the candidate; network mode |
| Models as used | trial `config.json` and `agent/trajectory.json` |
| External state | **volatile:** `$HARBOR_JOBS_DIR` = `${CAPEVOLVE_CI_CACHE}/harbor-jobs/<job>/<trial>/` (`config.json`, `result.json`, `agent/{trajectory.json,recording.cast,sessions/}`, `verifier/*`), else `/tmp/harbor_jobs_*`; job dirs older than 6 h are deleted by `ci_setup.sh`; `harbor_dataset_*` temp dirs; `TMPDIR` under the CI cache; npm cache `${CAPEVOLVE_CI_CACHE}/npm-cache`; containerd images in `/var/lib/containerd`; containers `*env-main*` (orphans removed by `ci_setup.sh`) |
| Sources | `benchmark-history` `*swebench*` runs and records, `runs/20{0,1,2}__full-swebench-verified/ui` (owner `avalappi`, made on another machine: `may_exist_at`); ledgers: as `_core.md` |
| Reproduce | Harbor CLI version (`uv tool install harbor`, unpinned); dataset name and version; Claude Code npm version per container (unpinned: record it from the trajectories); image digests; unpinnable: npm "latest" at run time |
| Licence | SWE-bench Verified: `unverified` (the HF card states none) |
| Secrets | as `_core.md` |
