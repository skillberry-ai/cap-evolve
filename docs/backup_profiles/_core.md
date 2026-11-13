# Backup profiles: values shared by every benchmark (from core)

Every profile in this folder adds to these values. A profile key whose value is "as `_core.md`" takes it from here.

- **Rollouts:** `rollouts/<split>/<task>__<cand>__t<k>.json`, holding `{input, rollout, score}`.
  `Rollout` has `cost_usd`, `tokens` (one total), `error`, `trace`, `tool_calls` and `metadata`.
  There is no per-episode latency in core.
- **Episode index:** `eval_index.jsonl`. Per-evaluation seconds are in the `evaluate` events. Run
  totals are in `state.json` `spent` (including `usersim_usd`, which is a list-price estimate already
  inside `usd`).
- **Infra errors:** core drops errored trials from the mean by default (`errored_trial_policy: drop`).
- **Test seal:** core seals test. In pooled mode, the sealed stratum is in `<project>.sealed/<run>/`
  or `$CAPEVOLVE_SEALED_DIR`.
- **Optimizer:** `claude -p … --allowedTools Bash` (`skills/optimizers/registry.yaml`). There is no
  sandbox unless the profile says so. Transcripts are in
  `~/.claude/projects/<slug of the work dir>/`, unless `CAPEVOLVE_OPTIMIZER_TRANSCRIPT` was set.
  Agent-mode runs also write `<run>/host/transcript.jsonl`.
- **CI:** the run dir is under `ci/benchmarks/.work/` and is wiped by the next run of the same
  tier×bench. If a tier has no `split_ids.json`, train = val = test (no holdout).
- **False positive in gold greps:** the term `ao_focus_canary`.
