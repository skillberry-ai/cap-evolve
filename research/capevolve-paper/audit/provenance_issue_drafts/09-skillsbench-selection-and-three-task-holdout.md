# SkillsBench 50.8 -> 84.2, 71.3% and 55.6 -> 66.7 are selection/fit or single-trial effects

## Problem
Post and draft quote 50.8 -> 84.2 across 87 tasks, "71.3% of tasks passed", and "55.6% to 66.7% on three unseen tasks".

## Evidence
`skillsbench-history:results/results.json` (`sk_recompute.py`): mean seed 0.5080, mean best 0.8422, best >= seed for all 87 (max over candidates); pass 64/87 either-split, 62/87 test-where-available (34 tasks with test, 45 of 64 passes val-only). On the 34 tasks with test: seed(val) 40.4, best(val) 72.8, test 68.7. `examples/skillsbench/run_full/final.json`: test 3 tasks x 3 trials, delta comes entirely from one trial of pptx-reference-formatting (2/3 -> 3/3), stderr 0.31/0.33. Run 20260903001 has sha null, event local.

## Impact
None is a generalisation estimate. The 3-task pilot is statistically empty and its tasks are in the 87-task sweeps.

## Correction
Report as "selection-maximised on optimized tasks"; replace 71.3% by the 34-task test result with CI; drop or heavily caveat the 3-task claim.

## Acceptance
A held-out SkillsBench result on >=20 never-used tasks with fresh trials, or the claim is removed.
