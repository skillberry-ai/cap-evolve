# recipes/v6/v6_g2_e1

The cap-evolve project config this run used — copied verbatim from the live project
(`parsec-intake_v6` worktree, `.capevolve/v6_g2_e1/project/`).

## What's here

- **`capevolve.yaml`** — the entire project config: `split_mode: pooled`, `promotion_rule: P2`,
  the group-sequential confirm-split test parameters (`p2_rung_sizes`, `p2_conf_n`,
  `p2_gs_looks`, `p2_dmin`), and the run's actual budget (`max_iterations: 10` — the run stopped
  at 6 by choice, not by hitting this cap; `stall: 0` — overridden from an initial `2` mid-run so
  a second consecutive reject would not auto-stop the search; see
  [`../../results/v6/v6_g2_e1/summary.md`](../../results/v6/v6_g2_e1/summary.md)'s "Why 6
  iterations" section).
- **`public_tasks.txt`** — the 67 **feedback (F)** task ids, the only ones ever visible to the
  optimizer during the run itself.
- **`split_ids.json`** — the full F/C/test partition: all 200 task ids, split into `feedback` (67),
  `confirm` (67), and `test` (66). Published openly, matching this benchmark's own task set, which
  is also being made public (dataset + results together, same convention as any benchmark that
  ships a train/val/test split). This run itself treated confirm and test as hidden from the
  *optimizer* during the search — the gate only ever saw an accept/reject bit, never a task id or
  score (see `../../results/v6/v6_g2_e1/summary.md`'s "Why there's no per-task F/C ledger") — but
  that is a property of how the search was run, not a secrecy claim about this file. If a future
  arm wants a fresh held-out set the current optimizer has never seen in any form, it needs new
  tasks added after this publication, not a re-hidden copy of this split.

## This is a hill-climb run, not a reuse measurement

Unlike `v5_g2_e1` (`max_iterations: 0`, scoring an already-optimized bundle with no further
search), this arm ran the optimizer loop itself: `optimizer_skill: claude-code`,
`algorithm_skill: hill-climb`, 6 iterations, 2 accepted. See
[`../../results/v6/v6_g2_e1/summary.md`](../../results/v6/v6_g2_e1/summary.md) for the full
account.

- **Models:** optimizer `claude-opus-5` (via `optimizer_skill: claude-code`), target/agent
  `claude-sonnet-4-6`.
- **Dispatch:** every F/C-split evaluation ran as a lane-queue job across up to 15 concurrent
  LSF workers (`examples/parsec/v6/adapters/adapter.py`'s dispatching adapter), not one
  `bsub`-per-task sweep like v4/v5's harness sweeps — this run used a single long-lived driver
  job that dispatched rollouts to the worker pool, resumed across several LSF jobs as earlier
  drivers hit their own budget slice and exited.
- **Task source:** `rhdp-parsec/v6_2026-10-16/` (the unified 200-task set — v4's 34 tasks plus
  v5's held-out 166, merged and renamed `bench-v6-*`, per
  `examples/parsec/v6/build_v6_tree.py` in the `parsec-intake_v6` worktree).
