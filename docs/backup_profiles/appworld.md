# Backup profile: `appworld` — `benchmarks/appworld/examples/react_agent`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | `success` (every requirement passes): binary. Success = `success`. Group metric SGC: per trial k, a scenario passes iff all its tasks pass (scenario = task-id prefix before `_`), averaged over k. TGC = mean task success. Analysis in `scripts/analyze.py`. |
| Infra rule | published: errors and missing cells count as failures (`analyze.py`); core search: drop. Detectors: `Rollout.error` "infrastructure: …", `metadata.infra_error`. |
| Telemetry | `prompt_tokens`, `completion_tokens`, `n_steps`, `termination`, `wall_seconds` / `episode_seconds`, all in rollout metadata; window: `runs/final/results.jsonl`. |
| Cost | agent: `cost_source="unpriced"` (RITS), `zero_means: unknown`. Optimizer: `state.json` `spent.optimizer_usd`, from the CLI. |
| Splits | train 90 / dev 57 / test_normal 168. Search split = train ∪ dev (fit). Test sealed by the adapter, scored in `scripts/final_window.py`. |
| Baselines | seed |
| Gold | `$AW_EVAL/root_full/data/tasks/*/ground_truth/` (`answer.json`, `compiled_solution.py`, `metadata.json`), `private_data`, `appworld/generate/`. Allowed to the optimizer: none. `root_opt` keeps train/dev ground truth: access to it is a finding to grade. Canary is release-wide, so only test ids count as evidence. |
| Isolation | `sandbox/` shim (bubblewrap or namespace), `progress/optimizer_guard.log`, `runs/isolation_check/*/report.json`, `scripts/isolation_gate.py`. |
| Agent evidence | per-episode `fs_probe`, `guard_blocked`, `guard_probe`. |
| Models as used | transcripts; window `results.jsonl`. |
| External state | `$AW_EVAL` (default `/tmp/aw_eval`, **volatile**): `root_opt`, `root_full`, `runs/` (manifest, final, isolation_check, optimizer_transcripts), `progress/`, `scratch/`, `reference/`, `lint_cache.json`. |
| Sources | posts: tracking issues. |
| Reproduce | launch: `scripts/setup_project.sh`, `capevolve.yaml`, `optimizer/INSTRUCTIONS.template.md`; data: `root_full`; clones: AppWorld @ `42b5bcf` + `patches/`; env: `venv-aw` freeze. |
| Licence | Apache-2.0; the protected part (API docs and implementations, solutions, tests, and `reference/api_index.md`) must not be published in plain text. |
| Secrets | the repo `.env`. |
