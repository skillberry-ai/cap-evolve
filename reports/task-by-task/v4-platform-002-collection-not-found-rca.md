# platform-002-collection-not-found-rca

<!-- BEGIN:auto -->

**task:** `platform-002-collection-not-found-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.883 |
| our baseline (v4_t1_e1) | test | 3 | 0.783 |
| seed (val, v4_t2_e1) | val | 5 | 0.907 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.117 · delta vs our baseline: 0.217

**T2 cost/time:** $8.30, 482,431 tokens, 1.95h (eval $1.34/393,252tok · optimizer $6.97/89,179tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433/report.md`, `.capevolve/v4_t2_e1_platform-002-collection-not-found-rca/run_20260920_034433/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Same two-hop RCA shape as platform-001, on a different failure: a missing Ansible role or collection whose cause is only visible in the execution environment's own `ansible.cfg`, not in the job log alone.

## What the optimizer tried

Single iteration (`cand_0001`) touching `aap2_agent.md`, `shared_context.md`, and `orchestrator.md`. It added a "Root Cause Category and Confidence" section (the taxonomy verbatim, a 10-row evidence-to-category table, two boundary rules for `dependency` vs `configuration`/`timeout_failure`), grew the AAP2 output contract from 4 to 6 required items so a verbatim category and confidence are always stated, added a new "Step 7d: Missing Collection or Role" pattern for stating what a fetched value does not include, and rewrote the Step 6 owner table to stop teaching a hardcoded (and forbidden) owner/repo pair.

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows `completion` and `tool_calls` were already 1.0 in all 5 seed trials; the entire 0.093 val gap was one missing `verdict.category` fact, missed in 3/5 trials (seeds 0, 1, 3) because the RCA taxonomy vocabulary appeared in none of the 8 prompt files — the seed wrote correct-sounding but non-taxonomy descriptions. The new taxonomy section and required output fields closed that gap, moving val 0.907 → 1.0 (Δ+0.093), with the RESULT line marking the task `fixed`. On the held-out test split, `report.md` records the baseline `seed` skills at 0.573 ± 0.055 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.427.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning — never checked against any other task (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md flags one live hazard the edit did not fix: `verify.py`'s exclusivity rule fails the verdict if a second taxonomy category token appears anywhere in the answer, so a thorough answer that rules out an alternative category by name would score zero — a risk the optimizer chose to leave as a hazard rather than address structurally this iteration.
