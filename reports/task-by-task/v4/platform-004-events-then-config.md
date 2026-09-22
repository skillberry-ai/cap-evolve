# platform-004-events-then-config

<!-- BEGIN:auto -->

**task:** `platform-004-events-then-config`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.733 |
| seed (val, v4_t2_e1) | val | 5 | 0.787 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.400 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.267

**T2 cost/time:** $15.88, 517,799 tokens, 2.05h (eval $1.22/357,549tok · optimizer $14.67/160,250tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427/report.md`, `.capevolve/v4_t2_e1_platform-004-events-then-config/run_20260920_083427/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A cluster-provision job failed. The task that actually failed, and the role it belongs to, only show up in the job's *events*, not in the log alone, and a config file supplies how many retries the wait was allowed. The seed also includes a second, successful host, so naming the wrong host is a distinguishable mistake.

## What the optimizer tried

Two iterations, both resolving one rule conflict: four different rules told the agent not to make a second `query_aap2` call after `get_job_log` (a redundant-call ban, a round budget, two re-fetch echoes in `shared_context.md`), while only one narrow rule said to make it — and that one lived in a GUID-discovery flow this task never enters, since a separate tip routes a direct job ID straight to `get_job_log`. `cand_0001` rewrote `aap2_agent.md`, `shared_context.md`, and `orchestrator.md` to make all of those rules agree (redundant now means same action *and* same arguments; a new Critical Rule 5 requires `get_job_events(failed_only=true)` after a failed job's log, before any GitHub fetch) and also fixed a `Role` field the report template required but no log in this task's trials could source. `cand_0001` was rejected on paper (val 0.400), but JOURNAL.md's post-mortem — reading all 5 trials' raw records rather than the aggregate — found this was a LiteLLM gateway outage: 2 of 5 trials scored 1.0 with the byte-identical prompt, and the other 3 never received a model response at all (TLS handshake timeouts and a 600s request timeout, before any output was produced). `cand_0002` re-delivered the same behavioral contract in about a third of the diff size (no changes to `orchestrator.md`) and was accepted at val 1.0.

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows all 5 baseline trials differ at exactly one decision point — whether a second `query_aap2` call happens after `get_job_log` — and that one skipped call costs both the `tool_calls` and `answer` components simultaneously (0.267 of reward). `cand_0002`'s conflict-resolved rules made that call fire consistently, moving val 0.787 → 1.0 (Δ+0.213) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.713 ± 0.008 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.287; the auto block's `delta vs JB` of 0.000 reflects that the single-trial JB baseline measurement already sat at reward 1.0, not that the optimizer made no difference against the team's own earlier (n=3) baseline of 0.733.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md's own account is a caveat on interpreting any single rejected candidate at face value: `cand_0001`'s val=0.400 looked like a regression but was actually 2 clean 1.0 trials plus 3 infrastructure failures (a gateway outage) that the eval layer scored as 0.0 — a distinction JOURNAL.md says the framework currently cannot make automatically (filed as a framework escalation).
