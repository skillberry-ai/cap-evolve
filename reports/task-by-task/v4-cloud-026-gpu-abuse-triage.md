# cloud-026-gpu-abuse-triage

<!-- BEGIN:auto -->

**task:** `cloud-026-gpu-abuse-triage`  
**category:** cloud  
**tranche:** regression  
**services:** cloud  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.808 |
| our baseline (v4_t1_e1) | test | 3 | 0.886 |
| seed (val, v4_t2_e1) | val | 5 | 0.940 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.907 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.977 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.192 · delta vs our baseline: 0.114

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620/report.md`, `.capevolve/v4_t2_e1_cloud-026-gpu-abuse-triage/run_20260919_141620/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Two candidates, both editing `security_agent.md` only. `cand_0001` fixed a single unmatched-tool-call gap (all 4 failing trials were missing a call to `query_marketplace_agreements`, having instead used `describe_marketplace`) by rewriting "when to use which" guidance, adding a Right/Wrong worked example, and a new "Triage an Account Flagged for Abuse" playbook. It was rejected (val 0.907, Δ −0.033) because per-trial decomposition showed it solved `tool_calls` (1.0 in 5/5) but broke `answer` by introducing the word "records" for CloudTrail's empty results, tripping the forbidden `overstated-attribution` check. `cand_0002` kept `cand_0001`'s tool-call fix verbatim and added a new section on how to word an empty CloudTrail result ("returned", never "records"), plus rules against speculative causal explanations for the gap.

## Why the winning candidate won

JOURNAL.md's per-trial reward-detail table shows `cand_0001` completely fixed `tool_calls` (1.0 in 5/5, up from 0.75×4/1.0×1 on seed) but 4 of 5 trials picked up a forbidden-word hit ("cloudtrail records") because `cand_0001`'s own new prose used that word. `cand_0002` removed the offending vocabulary, added an allow-listed sentence template for reporting an empty log source, and separated the timestamp from the unattributed actor to avoid a different forbidden n-gram — taking val from seed's 0.940 through `cand_0001`'s rejected 0.907 to `cand_0002`'s accepted 0.977 (test 1.0), fixing the marketplace tool-call gap without re-triggering the attribution check.

## Caveats

n=5 val trials; single-task tuning, never checked against other tasks (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md also records two hypotheses it explicitly refuted rather than assumed: a `lookup_events` fallback for the empty CloudTrail does nothing (CloudTrail is seeded empty by design), and negative/forbidden examples quoted in the prompt get echoed back by the agent rather than avoided.
