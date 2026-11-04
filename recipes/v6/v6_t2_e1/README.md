# v6_t2_e1 recipe (T-opt)

34 independent cap-evolve runs, one per train (feedback) task with Seed < 0.95 that the fast router
does not send to a specialist missing a required tool. Each run's `capevolve.yaml` is identical
except for the task id; [`capevolve.platform-004.yaml`](capevolve.platform-004.yaml) is one of them.

- Per task: hill-climb, 5 trials per candidate, at most 5 iterations, stall 2, stop at reward 1.0,
  $50 total / $20 optimizer budget, no finalize (train = val = test for a single task).
- Seed trials reused from `v6_g2_e1` (10 per task); not re-run.
- Optimizer sees the champion's trials plus the last rejected candidate's trials
  (`examples/parsec/v6_t2/stage_rejected.py`).
- Optimizer brief: [`optimizer_INSTRUCTIONS.md`](optimizer_INSTRUCTIONS.md). It names only the one
  task and does not mention merging or other tasks.
- Agent `claude-sonnet-4-6`, optimizer `claude-opus-5`; split from `../v6_g2_e1/split_ids.json`.

Scaffold and run with `examples/parsec/v6_t2/{scaffold_projects.py,run_t2.sh}` on `main`.
