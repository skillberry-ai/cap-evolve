# Backup profile: `rfe-creator` — `benchmarks/rfe_creator/template`; CI `rfe-creator`

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

| Key | Value |
|---|---|
| Reward | `_reward/judges.json` `reward`: a weighted mean of 10 checks and 2 LLM judges, continuous. **Success: undefined** (the overlay sets `gate: false`): `success` is `null` with that reason. Group metric: per judge (`raw.per_judge`). |
| Infra rule | published: drop. |
| Telemetry | `tokens` not set (`not_recorded`); no latency, steps or termination. |
| Cost | agent: `run_result.json` `cost_usd` (`reported`). **Judges:** not recorded anywhere, and billed on the optimizer's gateway (`aux_call`, `null` with that reason). |
| Splits | none: train = val = test (no holdout). |
| Baselines | seed |
| Gold | `rfe-creator/eval/dataset/cases/*/annotations.yaml`, judge prompts in `eval.yaml`. **The agent's worktree contains them.** |
| Isolation | none |
| External state | `$RFE_RUNS_DIR` (`/tmp/cap-evolve-rfe-creator/runs/`, **volatile**); worktrees; clones in `~/.cache/capevolve-ci/rfe-creator-src/`. |
| Reproduce | rfe-creator and agent-eval-harness at the recorded SHAs (reset to `main` on every setup: record them). |
| Licence | rfe-creator unlicensed; agent-eval-harness Apache-2.0. |
