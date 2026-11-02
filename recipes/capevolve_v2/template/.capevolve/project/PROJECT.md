# cap-evolve project — exp895 capevolve_v2 (SpreadsheetBench verified_400)

Fresh intake on cap-evolve main 75b3bcdd0 (PR #914) + cherry-picks 777e111b3 (#903 container retry) and 0d791eeb7 (common
helper gate); worktree `sbv400-k02`, branch `exp/sbv400-895-k02`, venv `exp895/venv_k02`. Issue skillberry-ai/cap-evolve#895.
Scaffold: `skills/phases/intake/scripts/run.py` (scratch in `../../intake_scratch`). Written by the [v2-session], 2026-10-25.

## What we're optimizing
- Capability: `[system-prompt, skill-package]`; artifact `seed_capability_v2` (byte-identical to the capevolve arm); edits: `[edit]`.

## How we run the target
- Agent: Gemma-4-31B on RITS (`target_model: google/gemma-4-31B-it`), via `adapters/adapter.py` (sha256 c035c75e…, identical to the capevolve arm).
- `adapters/model_config.py` sha256 2eac2eda… (identical).

## How we score
- SpreadsheetBench official checker via the adapter; reward in [0,1] = the benchmark's HARD score (hard_restriction: 1.0 only if every test case matches), with LibreOffice recalc. Set by SPREADSHEETBENCH_SCORING=hard, REWARD_RECALC=1 in node_env_k02.sh (same as the capevolve arm). The gate runs on this reward.
- Spec declares metric_primary: hard_restriction; metrics_display: [hard_restriction, soft_restriction] (display only, never gate). The adapter records soft/hard x recalc/no-recalc on every rollout.

## Data
- `dataset_source: adapter`; `split_ids.json`: train = val = 120 ids, test = []; `split_seed: 0`; `all_task_ids.txt` (400).
- Test is scored only in the common final window (`finalize: false`).

## Optimizer + algorithm
- Optimizer: `claude-code`, `rits/zai-org/glm-5-3`, max_turns 80, usd_per_iter 0, in the exp895 bwrap sandbox; `memory_skill: md-files` (also the new default).
- Algorithm: hill-climb, focus all, deterministic, `store: copy`, `gate_mode: paired`.
- Budget: max_metric_calls 2160 (= R), max_iterations 1000, stall 0, budget_reserve true, num_trials 3, errored_trial_policy fail.
- INSTRUCTIONS.md: new k02 template (196 lines) + the 77-line exp895 surface-contract block inserted after `{{BENCH_REPO}}`
  (line 47), same splice as the capevolve arm (one blank line before the block) = 273 lines, sha256 `c047435b418b8f1eb9da50f37a64fb50fcdd128601d24c8f26f6c88c322cb6c3`.
  All placeholders present with the stock counts ({{FAILURES}} twice, as in stock; every other once).

## Diff vs the `capevolve` arm (key: old -> new)
| key | old | new |
|---|---|---|
| gate_k_se | 0.5 | 0.2 (main default; not overridden) |
| gate_footprint | false | absent (main default: masking on; Osher) |
| optimizer INSTRUCTIONS.md | old main + addendum | PR #914 "Improvement 2" template + same addendum |
| code | exp/sbv400-895 (old main +2) | main 75b3bcdd0 + #903 + helper gate |
| RITS key | rits.env key | one dedicated key slot per seed (GW_RITS_KEY_SLOT) |
| run paths | runs/capevolve | runs/capevolve_v2 |
| metric_primary / metrics_display / metric_directions | empty | hard_restriction / [hard, soft] / [higher, higher] (declaration only; reward unchanged) |
Unchanged: capability/seed, optimizer, model, splits, trials, algorithm, budget, helpers/surface blocks (paths re-pointed).
Other template defaults that moved with main are taken as-is (not overridden).

## Inputs status
- NEEDED inputs resolved: tasks/scorer via adapter; split ids; seed capability.
- RECOMMENDED: metric_primary/metrics_display set to the SpreadsheetBench hard/soft scores (display only); github_integration false.
