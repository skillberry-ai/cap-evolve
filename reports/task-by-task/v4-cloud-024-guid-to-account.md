# cloud-024-guid-to-account

<!-- BEGIN:auto -->

**task:** `cloud-024-guid-to-account`  
**category:** cloud  
**tranche:** regression  
**services:** cloud  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.200 |
| our baseline (v4_t1_e1) | test | 3 | 0.200 |
| seed (val, v4_t2_e1) | val | 5 | 0.200 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.800 · delta vs our baseline: 0.800

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425/report.md`, `.capevolve/v4_t2_e1_cloud-024-guid-to-account/run_20260919_122425/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

The optimizer ran a single iteration (`cand_0001`) after first correcting the task's "flaky" label — all 8 trials on disk (5 in this run, 3 in an earlier run) scored an identical 0.2, i.e. deterministic, not noisy. It traced the failure to the orchestrator, which never delegated to a domain agent at all, so it rewrote `orchestrator.md` (a new "Bare Identifiers and Minimal Prompts" section teaching that a lone identifier-shaped message is a lookup request, a narrowed "Asking Clarifying Questions" rule, and a `query_aws_account_db` Direct Tools bullet) and `shared_context.md` (splitting the identifier-shape rule by question type).

## Why the winning candidate won

JOURNAL.md shows the seed's orchestrator had no rule turning a bare GUID-shaped token into a tool call, so it replied with a generic "I didn't quite catch that" and made 0 tool calls, scoring 0.2 on both val and test. After the rewrite the orchestrator calls `query_aws_account_db` and reports the matched row, taking val 0.2 → 1.0 and test 0.2 → 1.0 (delta +0.8), with the RESULT line marking it `fixed={cloud-024-guid-to-account}`. An adversarial audit before finalizing also caught and fixed a shape-matching bug (the rule as first drafted required a digit in the token; this task's actual token is all letters) that would otherwise have silently reproduced the original failure.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning: the edit was never checked against any other task (see `results/v4/summary.md`'s "Coverage" section on why a category/global merge regression-check matters). JOURNAL.md also flags an unresolved scaling risk it did not fix: `query_aws_account_db` has no `guid` filter, so a GUID lookup on the real (thousands-of-rows) pool is a client-side scan that "cannot be guaranteed to succeed" — the optimizer treats this as a tools-layer escalation, not something addressable by prompt text.
