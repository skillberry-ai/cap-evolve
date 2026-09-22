# platform-008-log-does-not-say

<!-- BEGIN:auto -->

**task:** `platform-008-log-does-not-say`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.933 |
| seed (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.067

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310/report.md`, `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Single iteration (`cand_0001`) rewriting `aap2_agent.md`, `shared_context.md`, and `orchestrator.md` after finding all 5 seed trials scored an identical 0.8 by missing the same graded fact (`no-root-cause`) for two different reasons: 3/5 trials fabricated a cause the evidence didn't support, and 2/5 got the right verdict but lost credit to markdown bolding breaking a literal substring match. The optimizer traced the fabrication to the prompt itself — `aap2_agent.md` said "Long = timeout," licensing a cause from elapsed time alone — and removed that licence, added a new "Does the evidence actually establish a cause?" step naming what does and does not establish a cause, added a "when no cause is established" output branch, and, after an adversarial review round caught that `orchestrator.md` never received the anti-bolding rule that lived only in the other two files, added the same plain-text formatting rule to `orchestrator.md`. This is a rerun (`run_20260920_144310`); the first attempt (`run_20260920_124829`) never finalized — its `state.json` shows 2 iterations spent and a best val of 0.96, but no `report.md`/`final.json` were ever written, consistent with `results/v4/summary.md`'s account of a budget-cap interruption.

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows the entire 0.2 val gap was one missing substring (`no-root-cause`) split across two sub-modes (a fabricated cause vs. a correct-but-bolded verdict); the licence-removal and the plain-text formatting rule (added to all three prompt files after the audit found `orchestrator.md` was the actual site of the bolding bug in 2/5 trials) closed both, moving val 0.800 → 1.0 (Δ+0.200) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.960 ± 0.040 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.040.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md notes the new `shared_context.md` "Reporting a Negative Finding" block is prepended to all six domain agents but was only exercised by this task's trials — the optimizer checked the other five domain files for contradictions and found none, but calls that "a reading, not a measurement."
