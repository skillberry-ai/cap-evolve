# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | A: job-status query uses the heavier log action | platform-126-stop-job-from-tower-jobs (~50% of trials) | `babylon_agent.md` "Checking Job Status" says to call "`get_job` **or** `get_job_log`" with NO criterion. Unguided either/or ⇒ ~coin-flip sampling. Contract expects `get_job`; `get_job_log` leaves `tool_calls` at 0.5 (ordered-subsequence still credits call 1), so reward 0.85 vs 1.0. `answer`=1.0 in every trial. | KNOWLEDGE (missing discriminating rule) | sharpen decision rule + worked example + fix response-format block |
| 2 | B: `query_aap2` response format is wrong/incomplete | same | Format block lists a non-existent `elapsed` and omits `failed` + `duration_seconds` — the exact fields the answer needs. Gives the agent a reason to believe only the log carries timing. | KNOWLEDGE | correct the documented field list |
| 3 | C (latent, NOT editable here): `aap2_agent.md` says "**Always** use `get_job_log` instead of `get_job`" (4 places) | n/a for this task | Flatly contradicts the contract for aap2-routed job-status tasks. **Not in this task's prompt footprint** — see escalation. | KNOWLEDGE | deliberately skipped (unmeasurable here) |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | KNOWLEDGE / decision policy | `babylon_agent.md` → new "Choosing between `get_job` and `get_job_log`" | 3-row decision table + explicit field-list rule: answerable from `status`/`failed`/`started`/`finished`/`duration_seconds`/`job_name`/`template_name`/`action`/`guid` ⇒ `get_job`; asks for a cause/error text/log contents ⇒ `get_job_log`. States the trigger is **what was asked, not whether the job failed**. | Yes — all 16 babylon-routed `get_job_log` siblings ask *why*, so they stay on the log. |
| A | BEHAVIORAL / worked example | `babylon_agent.md` | Worked example for the mechanism-level shape "a lifecycle action triggered from the portal appeared to hang; which job, which controller, did it work, when did it finish, how long" → ends in `action="get_job"` + "**Do not** call `get_job_log` here: nothing asked why." No GUID/cluster/host/job-id/duration from the task. | Yes — adds a case, loosens nothing. |
| B | KNOWLEDGE / output contract | `babylon_agent.md` response-format block | Real `get_job` fields documented; `get_job_log` described as "those same fields **plus** the `log` body". Removes the belief that timing requires the log. | Yes — purely corrective. |
| A | KNOWLEDGE | `babylon_agent.md` (`tower_jobs` docs + example step 1) | `tower_jobs` maps **each lifecycle action** to its own `{controller, job_id}`; different actions for one lab commonly sit on different controllers ⇒ read the entry for the action asked about. | Yes. |
| A | BEHAVIORAL / narrowing | `babylon_agent.md` multiworkshop bullet | The one unconditional "use `get_job_log`" narrowed to "when you need to explain *why* it failed", cross-referencing the new section, so it can't pull behaviour back. | Yes — still fires for RCA. |

## Verify-the-fix
- Failing trace `…/seed-9/1792151635583/…__hqGGazR/agent/agent.jsonl`: agent held `tower_jobs`, was asked status/finish/duration, emitted `action="get_job_log"`. At that exact decision point the old prompt gave a bare either/or AND a format block hiding `duration_seconds` from `get_job`. New text (a) tables that question-shape to `get_job`, (b) shows a worked example of the same shape ending in `get_job`, (c) shows `duration_seconds` present in `get_job`. All three bear on the token that went wrong.
- Control `platform-166` (babylon-routed, job **failed**, contract still wants `get_job`): refutes a "failed ⇒ log" rule. The "what was asked, not whether it failed" clause + the "**What** a job was doing" table row keep it on `get_job`.
- Discriminator validated by mining all 49 bench-v6 tasks expecting `get_job`/`get_job_log` and cross-tabulating vs routed agent: babylon+`get_job_log` = 16 (all RCA "why"), babylon+`get_job` = 2 (both metadata-only). Rule classifies 18/18 correctly.
- Non-overfit check: `grep -niE "m6qpz|heron|sap.hana|4419860|event0|6444|dkowalczyk|1h 47|107 min"` over both edited-footprint files → no hits.

## Process & features used
- One read-only Explore subagent to find the prompt-assembly code; I then **independently re-verified its central claim by executing `classify_fast` myself**, because that claim inverted which file to edit. No edit-subagents/worktrees: diagnosis collapsed to one mechanism in one file, so parallel edit-workers would add merge surface for zero coverage gain.
- **Footprint finding that changed the plan:** `task.toml` says `services=["platform"]`, which suggests `orchestrator.md` + `aap2_agent.md`. That is wrong. `system_prompt.py:116-121` builds a non-orchestrator prompt as `shared_context.md` + exactly ONE domain file; `orchestrator.py:1197-1214` takes a regex fast-path (`classify_fast`, `agents.py:256-282`) that runs one sub-agent with no orchestrator call and no delegation tool (hence no handoff in any transcript); `services` never influences prompt choice (only seeds, `install_seeds.py:93-106`). Executing `classify_fast` on this `instruction.md`: `_BABYLON_PATTERNS` matches "Babylon", `_AAP2_PATTERNS` does not → **`babylon`**. So the footprint is `shared_context.md` + `babylon_agent.md` only, and editing `aap2_agent.md` would have scored exactly zero.
- Prior iterations read: none exist (iteration 1; RUNMAP/LEDGER empty, `rejected.jsonl` has no entries).
- Evidence base: 31 graded trials on disk via `reward-detail.json`. `answer.required_missed` is `[]` in all of them; only `tool_calls` ever moves.

## Good things to PRESERVE (do not let a future iteration undo these)
- The two-call shape: `list_anarchy_subjects` with `guid` → ONE `query_aap2`. Trials that fanned out to `query_provisions_db` / `list_anarchy_actions` / `query_splunk` / `find_jobs` also scored 0.85 (seed-120002). Breadth is not rewarded here; do not add "investigate more" guidance to this path.
- Answer content/format — `answer`=1.0 in every single trial. The only addition was making the "hours/minutes **and** raw seconds" duration convention explicit, which passing trials already did.
- `shared_context.md` was left completely untouched: the fix is domain-specific, not domain-general.

## Deliberately skipped (cluster + why)
- Cluster C, `aap2_agent.md`'s "Always use `get_job_log` instead of `get_job`" (lines 60, 91, 95, 106): genuinely wrong for aap2-routed job-status tasks, but `aap2_agent.md` is **never loaded for this task**, so the gate cannot measure the change. A blind unmeasurable edit is how a plateau starts. Escalated below.
- `orchestrator.md`: not loaded (fast-path bypasses it). No edit could affect this task.

## Escalations (need code, not prose)
1. `classify_fast` routes a Babylon-flavoured AAP2 job question to the **babylon** agent, whose job-status guidance is a brief aside rather than a first-class concern. Fixing the routing needs a classifier/delegation code change; no prompt edit can.
2. `aap2_agent.md`'s blanket "always `get_job_log`" should be replaced with the same question-shape discriminator — but only by an iteration whose task actually routes to `aap2`, so the gate can score it.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` next to this file.
