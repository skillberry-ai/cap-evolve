# v2 Baseline — 10 authored bench-aap2 tasks

**Date:** 2026-08-13
**Model:** aws/claude-sonnet-4-5
**Simulator:** kaegis, one process per task, seeded per-task from `tasks_v2/*/seed.json`
**Task set:** 10 authored scenarios (schema bench/v2), no gold-trace lineage.
**Baseline JSON:** `baseline_all_1786651164.json` (epoch 1786651164)
**Trajectory root:** `trajectories/harbor-run/` (10 trial subdirs + job-level `config.json`, `job.log`, `lock.json`, `result.json`)

## Aggregate

| Metric | v1 (30 traced) | v2 (10 authored) |
|---|---|---|
| Mean reward | 0.240 | 0.087 |
| Stdev | 0.281 | 0.148 |
| Min / max | 0 / 1 | 0.000 / 0.400 |
| Wall clock | 36.4 min | 6.6 min |
| Infra errors | 0 / 30 | 0 / 10 |

Not directly comparable — different scoring schema (bench/v2 with per-task
weights vs v1's fixed 50/50 gate·traj+assert). Distribution shape is comparable.

## Per-task

| Task | Reward | Completion | Status |
|---|---|---|---|
| bench-aap2-001-single-job-outcome | 0.267 | 1.0 | ok |
| bench-aap2-002-failed-jobs-on-controller | 0.000 | 1.0 | ok |
| bench-aap2-003-never-started-explanation | 0.400 | 1.0 | ok |
| bench-aap2-004-failing-task-and-host | 0.000 | 1.0 | ok |
| bench-aap2-005-find-then-diagnose | 0.000 | 1.0 | ok |
| bench-aap2-006-log-root-cause | 0.000 | 1.0 | ok |
| bench-aap2-007-count-and-oldest | 0.000 | 1.0 | ok |
| bench-aap2-008-preceding-task | 0.000 | 1.0 | ok |
| bench-aap2-009-nonexistent-job | 0.000 | 1.0 | ok |
| bench-aap2-010-log-does-not-say | 0.200 | 1.0 | ok |

MEAN 0.087 · STDEV 0.148 · MIN 0.000 / MAX 0.400 · 10/10 ok · wall 395.3s (6.6 min).

## Reward distribution

| Bucket | Count | Bar |
|---|---|---|
| 0.00 | 7 | ####### |
| 0.01-0.24 | 1 | # |
| 0.25-0.49 | 2 | ## |
| 0.50-0.74 | 0 | |
| 0.75-0.99 | 0 | |
| 1.00 | 0 | |

## Notes

- Per-task sims: ports 9086-9095. Manifest at `.capevolve/project/sims-v2.manifest.json` (deleted at teardown).
- No SKILL.md edits vs v1 (byte-identical to upstream `aap2_agent.md`).
- Known gaps carried forward from v1: assertions still unreviewed (bench/v2 weights
  reallocate signal to `answer` fields, but the ground truth is still whatever JB's
  authoring team wrote).
- **Substantive baseline signal (gold-leak canary / tool-selection bias):** every one
  of the 10 tasks scored `tool_calls = 0.0`. The `seed_capability` aap2 SKILL.md
  consistently steers the agent toward `get_job_log` (which returns metadata + a
  trimmed log body) rather than the `get_job` call the tasks expect, and toward
  string `job_id` values where the expected type is int. Two of the three non-zero
  rewards (001 = 0.267, 010 = 0.200) scored on the `answer` sub-score alone; only
  003 = 0.400 combined `answer` with anything else. No SKILL.md changes are
  recommended here — v2's job was to establish the baseline, not to optimize.

## What v2 changed vs v1

1. Per-task simulator process (no cross-task sharing / no cross-task LLM context bleed).
2. Task-authored `seed.json` -> sim `db.json` (was: LLM-generated from OpenAPI spec).
3. bench/v2 verifier schema (was: v1 gate x 0.5*traj + 0.5*assertions).

## Security — before any public-remote push

Files under `trajectories/harbor-run/` (`config.json`, `lock.json`, and per-trial equivalents)
contain the internal LiteLLM gateway hostname
`https://ete-litellm.ai-models.vpc-int.res.ibm.com` verbatim. The API key is redacted
by harbor, the hostname is not.

Before `git push` to any public remote:
- Sanitize: `find trajectories/ -name '*.json' -exec sed -i.bak 's|https://ete-litellm[^"]*|https://<litellm-gateway>|g' {} +` (then `find trajectories/ -name '*.bak' -delete`)
- OR exclude: add `trajectories/harbor-run/**/*.json` to a commit-time filter
- OR skip commit of `trajectories/` entirely — the `baseline_all_*.json` + `summary.md` + `run.log` are the reader-facing artifacts.
