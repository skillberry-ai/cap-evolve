# Backup profile: `swebench-verified-harbor` and `harbor-<dataset>` — `benchmarks/generic/harbor/template`; CI `swebench`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | verifier `reward.json` / `reward.txt` (possibly partial). Success: reward ≥ 1. Group metric: repo, from the instance-id prefix. |
| Infra rule | published: drop. Detector: `exception_info` with no reward. |
| Telemetry | trial `result.json` `stats` (input, output and cache tokens separately); latency per `harbor run` only. |
| Cost | agent: CLI-reported in `result.json` (`reported`). |
| Splits | CI full 100/50/100 (`split_ids.json`); pilot and smoke: fit. |
| Baselines | seed |
| Gold | task `tests/test.sh`, `solution/solve.sh` in Harbor's task cache; trial `verifier/`. |
| Isolation | none; the container network is public. |
| Agent evidence | packaged mode runs `/capability/score.sh` from the candidate (check that the grader is not candidate-supplied); registry mode delivers only `prompt.md` (B2 "capability as delivered"). |
| External state | `$HARBOR_JOBS_DIR/<job>/<trial>/` (**volatile: reaped after 6 h** by CI setup); containerd images; npm cache. |
| Reproduce | Harbor CLI version; dataset name and version; Claude Code npm version per container (unpinnable unless recorded). |
| Licence | SWE-bench Verified: none stated on its card. |
