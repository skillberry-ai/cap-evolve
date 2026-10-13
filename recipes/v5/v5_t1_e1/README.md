# recipes/v5/v5_t1_e1 (discarded run)

The cap-evolve project config the discarded `v5_t1_e1` sweep used. It is identical to the baseline's
([`../v5_b1_e1/`](../v5_b1_e1/)) — `max_iterations: 0`, 5 trials, one task per project, `train ==
val == test` — so the recipe was not the problem.

**The problem was the artifact.** Each project's `seed_capability/` was filled from the live
`parsec-live` clone's `config/prompts/`, which held `v4_g_e1/rejected/cand_0001` (a v4 global-optimizer
candidate) rather than the original skill. See
[`../../../results/v5/v5_t1_e1/summary.md`](../../../results/v5/v5_t1_e1/summary.md).

## What's here

- **`capevolve.yaml`** — the per-task project config, byte-identical across all 68 tasks.
- **`split_ids.json`** — one representative copy; each task's real file substitutes its own id.

## How it ran

68 `bsub` jobs on CCC/LSF via `scripts/parsec/v5/fan_out.sh` in the `parsec-intake_v5` worktree,
5 → 10 → 13 concurrent, one task per node; `run_one_eval.sh` brought up a per-job lane and handed off to
`run_ccc_experiment.sh --max-iterations 0`. Agent `claude-sonnet-4-6`, simulator LLM `azure/gpt-5.4`.
Task source: the `v5_2026-10-10` drop's 68 tasks.

## No `seed_capability/` here

The skill this run actually evaluated is already in this branch, byte-identical, at
[`../../../artifacts/v4/v4_g_e1/rejected/cand_0001/`](../../../artifacts/v4/v4_g_e1/rejected/cand_0001/).
It is not duplicated under `artifacts/v5/`, which holds the verified original skill.
