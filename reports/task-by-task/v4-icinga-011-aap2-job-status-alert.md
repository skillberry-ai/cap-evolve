# icinga-011-aap2-job-status-alert

<!-- BEGIN:auto -->

**task:** `icinga-011-aap2-job-status-alert`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/run_20260919_202845` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.860 |
| our baseline (v4_t1_e1) | test | 3 | 0.953 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.140 · delta vs our baseline: 0.047

**T2 cost/time:** $12.77, 743,549 tokens, 0.88h (eval $2.41/694,680tok · optimizer $10.37/48,869tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/run_20260919_202845/report.md`, `.capevolve/v4_t2_e1_icinga-011-aap2-job-status-alert/run_20260919_202845/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

A single candidate (`cand_0001`) against `icinga_agent.md` and `shared_context.md`, after first showing the "flaky" label was wrong: all 5 val trials scored exactly 0.860 with zero variance, missing the identical answer item (`live-alert`) every time. It rewrote the Output Format's `Acknowledged`/`In Downtime` label pair into a full-sentence `Suppression:` line, made an empty comments/downtimes result a reportable finding rather than a silent non-event, and added a new "Reporting Suppression State" section.

## Why the winning candidate won

report.md and JOURNAL.md trace the miss to the agent's own output template, which had literally instructed the label form that fails the grader. An adversarial review of the first draft caught that its anti-pattern table quoted the forbidden phrasings directly — since the `invented-suppression` forbidden check has no exemption and matches any sentence, quoting those phrases would have converted "a likely +0.14 into a likely 0.00." The optimizer replaced the blocklist with a positive whitelist of 6 approved phrasings naming no forbidden string, verified each individually against the task's real `verify.py` (all scoring 1.000), taking val 0.860 (seed) → 1.000 (`cand_0001`, Δ +0.140; test also improves 0.86 → 1.0 per the table above).

## Caveats

n=5 val trials; single-task tuning, never checked against other tasks (see `results/v4/summary.md`'s "Coverage" section).
