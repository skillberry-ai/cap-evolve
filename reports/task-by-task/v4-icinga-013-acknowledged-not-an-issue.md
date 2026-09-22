# icinga-013-acknowledged-not-an-issue

<!-- BEGIN:auto -->

**task:** `icinga-013-acknowledged-not-an-issue`  
**category:** icinga  
**tranche:** regression  
**services:** icinga  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.480 |
| our baseline (v4_t1_e1) | test | 3 | 0.373 |
| seed (val, v4_t2_e1) | val | 5 | 0.448 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.608 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.000 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.640 |
| final (test, v4_t2_e1) | test | 5 | 0.640 |

delta vs JB: 0.160 · delta vs our baseline: 0.267

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/report.md`, `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/JOURNAL.md`

<!-- END:auto -->

## What the optimizer tried

Three candidates against `shared_context.md`, `babylon_agent.md`, and (unused) `icinga_agent.md`, after finding via direct code inspection that this alert's pasted service name ("Babylon Schema YAML Diff") matches `\bbabylon\b` and gets fast-path-routed to the Babylon agent before `orchestrator.md` or `icinga_agent.md` are ever loaded. `cand_0001` added a "no tool for the system being asked about" section (give the verdict from the evidence in the request rather than just refusing) and status-reading rules to `shared_context.md`, plus a Babylon-agent guard against re-framing an out-of-scope alert as a Babylon question. `cand_0002` wrote no JOURNAL.md entry of its own — the framework's synthesized note and `events.jsonl` show it was an infrastructure failure (an API error, "ENOTFOUND") that made zero capability edits to the prompt, not a rejected hypothesis. `cand_0003` rewrote the verdict-wording rule again, replacing a hedged "qualified verdict" instruction with a rule to state the verdict with no qualifier inside the sentence itself, mirroring the requester's own wording.

## Why the winning candidate won

JOURNAL.md derives an exact prompt-space ceiling from the grader: with the routing bug locking out the `query_icinga` calls and the `ticket` answer item unreachable, the maximum honest score is reward 0.64 (answer 4/5). `cand_0001` (val 0.608, Δ +0.160) fixed the "not-a-problem" verdict item on 4 of 5 trials, but seed-0 still lost the item on wording alone (an adverb inside "not currently actionable" and "is required" instead of the accepted "is needed"). `cand_0003` (val 0.640, Δ +0.032 over `cand_0001`) closed that gap by walking seed-0's exact failing sentences against the new rule and adding four independently-sufficient accepted phrasings, reaching the measured prompt-space ceiling of 0.64 (test also 0.64 per the table above, vs. baseline 0.48).

## Caveats

n=5 val trials (n=1 for the rejected `cand_0002` — its Δ is not a stable measurement, and JOURNAL.md explicitly says its 0.000 score reflects an unrelated infrastructure error, not a refuted prompt hypothesis). Single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md states the remaining gap to 1.0 (0.36 of reward) is a `classify_fast` routing defect requiring a code fix — the same class of routing bug documented for `icinga-010-stuck-anarchysubjects` above — and that further prompt iteration on this task is "close to worthless" without it.
