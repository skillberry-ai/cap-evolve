# platform-022-job-on-no-controller

<!-- BEGIN:auto -->

**task:** `platform-022-job-on-no-controller`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.700 |
| our baseline (v4_t1_e1) | test | 3 | 0.700 |
| seed (val, v4_t2_e1) | val | 5 | 0.595 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.895 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.930 |
| cand_0003 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.300 · delta vs our baseline: 0.300

**T2 cost/time:** $25.90, 764,975 tokens, 1.59h (eval $1.52/451,487tok · optimizer $24.37/313,488tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840/report.md`, `.capevolve/v4_t2_e1_platform-022-job-on-no-controller/run_20260920_201840/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An incident write-up claims a specific job failure caused an outage, and the task is to verify that claim against two named controllers before it gets published. The job doesn't actually exist on either controller, and the instruction quotes the false claim directly, so an honest answer has to both repeat it and refute it rather than confirming a job that was never run.

## What the optimizer tried

Three iterations, all edits confined to the same three files across the whole run (`aap2_agent.md`, `shared_context.md`, `orchestrator.md`). `cand_0001` diagnosed that `tool_calls` was 0.0 in 5/5 seeds not from flakiness but because the prompt itself mandated the wrong AAP2 action ("Always use `get_job_log` instead of `get_job`" appeared twice, plus "use `get_job_log` directly" once): it added a new "Choosing `get_job` vs `get_job_log`" section making the action conditional on the identifier's provenance (a system record → log; a write-up/ticket/chat/recollection → probe with `get_job` first), rewrote the three contradicting blanket mandates, and added matching "Verifying a Claim That Came From Somewhere Else" phrasing rules (with ✅/❌ exemplars) to both `shared_context.md` and a self-contained copy in `orchestrator.md` (which does not read `shared_context.md`). `cand_0002` found that `cand_0001`'s new phrasing rules had moved `tool_calls` 0.0→1.0 but left `answer` exactly flat (0.85 mean, unchanged), because Rule 2 was gated on "once a lookup shows the entity does not exist" — a precondition the mock's fabricated-record behavior never actually satisfied — and because its own ✅ exemplars didn't cover the verifier's accepted absence wording; it rewrote Rule 2 as an ungated, mechanical word-adjacency test and added a plain-words existence-verdict Rule 1. `cand_0003` (the final winner) replaced Rule 2 again, this time restructuring it from a blacklist of banned phrasings into a "two-homes" whitelist: the disputed job ID may appear in exactly two places (a status-table cell, or the Rule 1 existence verdict) and nowhere else, with every other mention replaced by a placeholder like `that job ID` or `[ID to be confirmed]`; it also rewrote Rule 3, changed the pre-send check from "re-read" to "COUNT", and made matching fixes in `orchestrator.md` and `aap2_agent.md`'s worked example.

## Why the winning candidate won

JOURNAL.md's own mechanism trace for `cand_0003` explains the win directly: rather than trusting only its own 5 val trials, the implementer replayed the real checker over all 15 archived trials from all three generations (seed, `cand_0001`, `cand_0002`) and found 7 forbidden-substring violations, each in a *different* location — a parenthetical gloss, a strikethrough blockquote, a padded attribution, a drafted-replacement clause — meaning "no two generations fail in the same place." A blacklist of banned phrasings can never converge on a moving target like that; capping the *number* of places the disputed ID is allowed to appear (two, both enumerable) removed all 7 historical violations at once rather than adding an eighth exemplar to dodge. Val moved 0.595 (seed) → 0.895 (`cand_0001`) → 0.930 (`cand_0002`) → 1.000 (`cand_0003`, Δ+0.070 over its parent). On the held-out test split, `report.md` records the baseline `seed` skills at 0.665 ± 0.035 versus the optimized skills at 1.000 ± 0.0 — a test-side improvement of +0.335. This task's val-seed score (0.595) is not the same number as its test-seed score (0.665); the two splits disagree even though the final optimized skills scored a clean 1.0 on both.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning. Both `cand_0002` (Δ+0.035) and `cand_0003` (Δ+0.070) are individually flagged by the framework's own RESULT line as `unresolved={platform-022-job-on-no-controller}` — each move measured less than 2×SE of its own measurement — even though this is the one task the run was tuning on. `cand_0002`'s JOURNAL entry escalated a mock-fabrication defect in the platform MCP server (`get_job` inserting a synthetic record for an unseeded job id, then failing the second controller with a duplicate-key error); `cand_0003`'s entry explicitly corrects that escalation as non-reproducing in its own 5 trials ("Either the backend was fixed between runs or it is seed-dependent; I did not find the cause, only that it does not reproduce") — a useful reminder not to treat an escalation note as a permanent fact. A separate tool-layer ambiguity escalation stands unresolved throughout the run: `get_job` and `get_job_log` are documented as returning the same metadata (one just adds the log), so the entire +0.300 gain from `cand_0001` is prose compensating for a tool-schema gap rather than a durable fix.
