# icinga-010-stuck-anarchysubjects

<!-- BEGIN:auto -->

**task:** `icinga-010-stuck-anarchysubjects`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.495 |
| our baseline (v4_t1_e1) | test | 3 | 0.402 |
| seed (val, v4_t2_e1) | val | 5 | 0.467 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.495 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.495 |
| final (test, v4_t2_e1) | test | 5 | 0.495 |

delta vs JB: 0.000 · delta vs our baseline: 0.093

**T2 cost/time:** $28.12, 1,477,226 tokens, 1.59h (eval $4.08/1,243,007tok · optimizer $24.05/234,219tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/report.md`, `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An Icinga alert reports AnarchySubjects stuck on a host. The task is to check the service's state and any suppression (comments or downtimes), then read the actual check script on GitHub to learn its configured critical threshold and report by how much the current value exceeds it -- grounding the verdict in configuration rather than the alert's own wording.

## What the optimizer tried

Two candidates against `orchestrator.md`, `shared_context.md`, `icinga_agent.md`, and `babylon_agent.md`. `cand_0001` initially diagnosed a missing Icinga entry in `orchestrator.md`'s Routing Guidelines (the alert's Babylon-sounding hostname routes it to the wrong domain agent) and added routing, suppression-reporting, and threshold-reporting rules — then, mid-iteration, found via direct code inspection that `orchestrator.md` and `icinga_agent.md` are never loaded for this task at all: a regex fast-path (`classify_fast`) dispatches straight to the Babylon agent before the orchestrator prompt is ever read. It pivoted to editing `babylon_agent.md` instead, adding a defer-guard against substituting a live measurement for the monitoring value the alert actually asked about. `cand_0002` made three further edits to `icinga_agent.md` (an explicit call-order table, a conditional step, and a consolidated "start from the user's location" rule) while stating up front that these are unmeasurable — `icinga_agent.md` contributes 0 characters to this task's prompt.

## Why the winning candidate won

JOURNAL.md derives the task's exact reward ceiling from the grader's own arithmetic: with the routing bug locking out all three `query_icinga` calls (`tool_calls` stuck at 0.25) and two of five answer items structurally unreachable, `0.3·0.25 + 0.7·(3/5) = 0.495` is the maximum honest score — identical to `cand_0001`'s measured val and to every individual trial's reward, with zero cross-trial variance. `cand_0001` was accepted (val 0.495, Δ +0.028 over seed's 0.467) purely by fixing the one answer item reachable from `babylon_agent.md` (no longer inventing a suppression state); `cand_0002` was rejected (Δ +0.000) because its edits all landed in the unloaded `icinga_agent.md`. The optimizer explicitly declined an available +0.14 move (a rule that would make the agent assert "nobody has commented on it" without ever reading comments) because it would score higher only by fabricating an unread suppression state — the mirror image of the check the rubric enforces in the other direction.

## Caveats

n=5 val trials; single-task tuning (see `results/v4/summary.md`'s "Coverage" section). This is a case where the optimized skill actually scored *below* the seed on the held-out test split even though it won on val: report.md records held-out test 0.495 for the optimized skills vs. 0.523 for the baseline seed skills on this run (test improvement −0.028) — a val→test overfit in the opposite direction from most other tasks in this batch. JOURNAL.md is explicit that the remaining gap to 1.0 is not a prompt problem: it traces the ceiling to the `classify_fast` regex-ordering defect that misroutes this alert to the Babylon agent before the Icinga agent's tools are ever reachable, and states that roughly half the reward is "locked behind the router defect" and needs a code fix, not further prompt iteration.
