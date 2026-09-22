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

**T2 cost/time:** $42.00, 2,440,673 tokens, 2.54h (eval $6.45/2,065,969tok · optimizer $35.55/374,704tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/report.md`, `.capevolve/v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/JOURNAL.md`

<!-- END:auto -->

## Why this task has two runs

A team-wide LLM API budget cap ("Budget has been exceeded") fired partway through this task's first attempt (`run_20260920_103719`) on 2026-09-20, but that run had already finalized cleanly before the errors mattered — 3 candidates, monotonic improvement, held-out test `1.0 ± 0.0`. It was re-run anyway (`run_20260920_162208`); the rerun's *seed* happened to score higher on validation that time (0.604 vs. 0.32), so neither of its 2 candidates beat it and it finalized at a mediocre `0.346`. `results/v4/results.json` takes the run with the best finalize `test_reward` across all of a task's finalized runs (not simply the latest), so the numbers above are from the first run; the rerun's material is vendored under `artifacts/v4/platform-005-wrong-owner-trap/discarded/run_20260920_162208-*/` for the record, not as this task's result.

## What the optimizer tried

For the canonical run (`run_20260920_103719`), all three candidates' JOURNAL.md entries are framework-synthesized "EMPTY HANDOVER" placeholders — the optimizer never wrote its own iteration entry for `cand_0001`, `cand_0002`, or `cand_0003`. `events.jsonl` shows why: each of the three optimizer subprocesses hit the same team-wide budget cap ("API Error: Request rejected (429) · Budget has been exceeded!") while composing its handover, so no rationale for what changed or why survives in this run's record. What is known is the measured outcome: val rose monotonically across all three candidates (seed 0.320 → cand_0001 0.608 → cand_0002 0.916 → cand_0003 1.000, the last one accepted as champion), with each RESULT line stamped `ACCEPTED (new champion)`.

## Why the winning candidate won

No content-based rationale is available for this task — better to say so than to invent one. JOURNAL.md contains no iteration entry for any of the three candidates (all three are framework-synthesized "empty handover" notes citing the optimizer's own budget-cap failure), so the only record of why `cand_0003` won is the reward progression itself: it reached val 1.0 with a paired Δ of +0.084 over `cand_0002`, and `report.md` records a held-out test score of 1.0 ± 0.0 for the optimized skills versus 0.774 ± 0.138 for the baseline `seed` skills (test improvement +0.226).

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). Beyond the usual caveats, this task's entire optimization record for the winning run is a rewards-only trail — no JOURNAL.md entry explains what any of the three candidates' prompt edits actually were, only that each was measured and accepted. That is an infrastructure gap (a budget cap firing mid-write), not evidence the edits themselves were arbitrary or wrong — the monotonic val progression and the clean held-out test score argue the edits were real, just undocumented.
