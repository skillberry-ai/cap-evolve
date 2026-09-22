# platform-005-wrong-owner-trap

<!-- BEGIN:auto -->

**task:** `platform-005-wrong-owner-trap`  
**category:** platform  
**tranche:** regression  
**services:** github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719` (n_runs: 2)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.813 |
| seed (val, v4_t2_e1) | val | 5 | 0.320 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.608 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.916 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.187

**T2 cost/time:** $13.65, 2,351,554 tokens, 1.55h (eval $7.26/2,303,144tok · optimizer $6.39/48,410tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/report.md`, `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Asks to look up a catalog item, find the AgnosticD content repository it points to, and read a workload role's defaults file from it. The trap is the single most common real mistake in the underlying trajectory corpus: fetching from the wrong repository owner (`rhpds/agnosticd-v2`, which doesn't exist) instead of the correct `agnosticd/agnosticd-v2`.

## What the optimizer tried

This task has two finalized runs (see `results/v4/summary.md`'s "Data-quality caveats"); `results.json` takes the one with the best held-out `test_reward`, which is this task's first attempt. All three of its candidates' JOURNAL.md entries are framework-synthesized "EMPTY HANDOVER" placeholders — the optimizer never wrote its own iteration entry for `cand_0001`, `cand_0002`, or `cand_0003`, because an unrelated infrastructure interruption hit each of the three optimizer subprocesses while it was composing its handover, so no rationale for what changed or why survives in this run's record. What is known is the measured outcome: val rose monotonically across all three candidates (seed 0.320 → cand_0001 0.608 → cand_0002 0.916 → cand_0003 1.000, the last one accepted as champion), with each RESULT line stamped `ACCEPTED (new champion)`.

## Why the winning candidate won

No content-based rationale is available for this task — better to say so than to invent one. JOURNAL.md contains no iteration entry for any of the three candidates (all three are framework-synthesized "empty handover" notes), so the only record of why `cand_0003` won is the reward progression itself: it reached val 1.0 with a paired Δ of +0.084 over `cand_0002`, and `report.md` records a held-out test score of 1.0 ± 0.0 for the optimized skills versus 0.774 ± 0.138 for the baseline `seed` skills (test improvement +0.226).

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). Beyond the usual caveats, this task's entire optimization record is a rewards-only trail — no JOURNAL.md entry explains what any of the three candidates' prompt edits actually were, only that each was measured and accepted. That is an infrastructure gap, not evidence the edits themselves were arbitrary or wrong — the monotonic val progression and the clean held-out test score argue the edits were real, just undocumented.
