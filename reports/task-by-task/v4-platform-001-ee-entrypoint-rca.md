# platform-001-ee-entrypoint-rca

<!-- BEGIN:auto -->

**task:** `platform-001-ee-entrypoint-rca`  
**category:** platform  
**tranche:** regression  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.520 |
| our baseline (v4_t1_e1) | test | 3 | 0.713 |
| seed (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.940 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.952 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.480 · delta vs our baseline: 0.287

**T2 cost/time:** $38.30, 866,365 tokens, 3.61h (eval $1.93/548,561tok · optimizer $36.38/317,804tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/report.md`, `.capevolve/v4_t2_e1_platform-001-ee-entrypoint-rca/run_20260920_000803/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Two iterations rewriting `aap2_agent.md` (plus a narrow `orchestrator.md` exception and a `shared_context.md` fix). `cand_0001` added a new "Step 9: Assign Exactly One Root Cause Category" — the 13-token taxonomy verbatim, an evidence-to-category table, and required `Category`/`Confidence` output fields — after finding the seed missed the graded `verdict.category` fact in 5/5 trials; it also replaced a hardcoded owner table with "parse the owner from a tool result, never recall it." `cand_0002` kept those edits and added two new Critical Rules forcing `lookup_catalog_item` to run before any GitHub fetch and reframing an empty GitHub result as usually a path problem rather than a wrong-owner problem — after an adversarial audit caught the first draft of that second rule pointing the opposite way (it would have licensed exactly the owner-substitution reflex that produced forbidden-owner calls elsewhere in the baseline run).

## Why the winning candidate won

JOURNAL.md's per-trial detail (`reward-detail.json`) shows the seed missed `verdict.category` in 5/5 trials, worth the entire 0.14 val gap; `cand_0001`'s taxonomy fix closed it, moving val 0.86 → 0.940. That left `tool_calls` short in 3/5 trials because `lookup_catalog_item` fired late or not at all before the GitHub fetch; `cand_0002`'s ordering rules closed that, moving val to 0.952 — though the RESULT line marks this last move as "unresolved" (too small relative to its own measurement noise to count as proven). On the held-out test split, `report.md` records the baseline `seed` skills at 0.644 ± 0.091 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.356.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning — the edit was never checked against any other task (see `results/v4/summary.md`'s "Coverage" section). `cand_0002`'s own audit trail is worth noting as a caveat on the process, not just the result: its first draft of the "empty result" rule was written backwards and, per JOURNAL.md's own count, would have reproduced the exact owner-substitution failure it was meant to fix — caught only because a subagent auditor challenged an unverified frequency claim before the candidate was finalized.
