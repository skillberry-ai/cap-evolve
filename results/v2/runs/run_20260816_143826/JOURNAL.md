# JOURNAL — optimizer handover (append-only, whole run)

YOU (the optimizer) own this file. It is the running, accumulating handover across ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you APPEND one new entry at the bottom (under the marker line); you do NOT edit or delete earlier entries. Read the whole journal before proposing, so you build on EVERY prior attempt (not just the last accepted one) and never re-test a refuted idea.

You CANNOT know your own gate result while you write — the harness scores you AFTER you stop and stamps a **RESULT** line (outcome + Δ + the EXACT tasks you broke/fixed) right below your entry. So do NOT write 'what worked' as a guess. To learn what actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to drop or redesign — its diff.patch is in ./prior_iterations/<id>/.

Append your entry for THIS iteration below the marker, using this shape (INTENT only — the framework appends the RESULT):

    ## Iteration <your candidate id> — <one-line headline of what you tried>
    - Changes I made (1 line per edit; name the file/tool + cluster it targets):
    - Per change, the EXPECTED effect + why it's safe (which failing task it should fix;
      why no passing task changes behavior):
    - Building on prior RESULTS: which prior entries' broke/fixed I used, and what I
      did NOT re-try because a prior RESULT showed it regressed (cite ids):
    - Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test):
    - High-value clusters still NOT cracked (and the guard/tool designs already tried):
    - Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch
      to — e.g. a NEW composite tool instead of another guard, or prompt instead of code):
    - Focus next iteration:

## Iteration cand_0001 — Add retry-on-transient-MCP-error rule and clarify get_job_log→get_job fallback for pre-execution errors
- Changes I made (1 line per edit; name the file/tool + cluster it targets):
  - SKILL.md `## Critical Rules`: added Rule 5 "Retry once on transient MCP errors" with a worked `<example>` block using the exact `Session expired: idle_timeout_exceeded` pattern from bench-aap2-001; also added a parenthetical to Rule 4 clarifying that a retry after a failed call is NOT a re-fetch. (Cluster 1: agent gives up after one transient error.)
  - SKILL.md `### Tips` (get_job_log bullet): replaced the misleading absolute "Always use `get_job_log` over `get_job`" with a conditional rule — start with `get_job_log`, and if the response has empty log (`log_original_size: 0`) AND lacks `status`/`started`/`job_explanation`, fall back to `get_job` for full metadata. (Cluster 2: pre-execution errors return an empty-log shape that the "always" rule stalls on.)
  - SKILL.md `### Investigation Flow` step 4: aligned the second occurrence of the "Always use get_job_log instead of get_job" wording with the fallback rule so the two locations do not contradict.
  - SKILL.md `## Tool Response Formats` (query_aap2 block): corrected `get_job_log`'s return-shape description to reflect BOTH the empty-log shape (`{job_id, controller, log, log_original_size, log_trimmed_size}`) and the normal-metadata shape, added the actual `get_job` field list observed in bench-aap2-003, and cross-referenced Critical Rule 5 for transient responses.
- Per change, the EXPECTED effect + why it's safe:
  - Rule 5 (retry): should raise bench-aap2-001-single-job-outcome's reward from 0.533. Task 001 hit `Session expired: idle_timeout_exceeded` on its first `get_job_log(controller="prod0", job_id=90142)` call and reported the failure to the user; with Rule 5, the agent will retry the same call and (per the bench-aap2-003 evidence) the retry succeeds. tool_calls score (currently 0.0) should reach 1.0 and the answer substrings should match once real metadata is available.
  - Rule 5 SAFE: bench-aap2-003 already retries a session_expired error and scored 1.0 — the explicit rule matches its observed behavior, so no behavior change on that task. On any passing task where the FIRST call succeeds, the retry rule never fires (bounded blast radius: only the transient-error branch is affected).
  - get_job_log fallback (Tips + Investigation Flow + Tool Response Formats): should not regress anything. Task 003 already did exactly this two-step pattern to score 1.0; making it explicit codifies known-good behavior. The fallback only fires when the empty-log condition is true, so any task whose first `get_job_log` returns non-empty metadata is unaffected.
  - No global permission/refusal rule was loosened. The "ask user to double-check the number before sweeping all controllers" decision rule was preserved verbatim — safe with respect to the run's declared focus task `bench-aap2-009-nonexistent-job`.
- Building on prior RESULTS: which prior entries' broke/fixed I used, and what I did NOT re-try because a prior RESULT showed it regressed (cite ids): none — this is the seed iteration (RUNMAP + LEDGER report "no prior iterations yet"). No prior RESULTs to build on and no refuted edits to avoid.
- Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test): none yet.
- High-value clusters still NOT cracked (and the guard/tool designs already tried):
  - `bench-aap2-009-nonexistent-job` — no trajectory available in `./trajectories/` this iteration (only 001 and 003 are present). Kept the existing "ask user to double-check the number" rule for that class; no design attempted yet.
  - Only 2 trajectories are visible; there may be additional clusters (find_jobs, get_job_events, catalog lookup, etc.) not exercised by the seed traces. Deferred until traces expose them.
- Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch to — e.g. a NEW composite tool instead of another guard, or prompt instead of code): N/A — first iteration. If the next RESULT stalls, next lever to try would be a composite tool (`get_job_summary` that internally does get_job_log→fallback→get_job) once the artifact space includes Python tools — the current candidate is prompt-only.
- Focus next iteration: after the framework stamps a RESULT for this candidate, read the newly-exposed trajectories for `bench-aap2-009-nonexistent-job` and any other tasks that appear, and cluster their failures. If Cluster 2 keeps recurring despite the prose rule, that is evidence the pattern needs deterministic enforcement (composite tool) rather than more prompt text.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=1.000 Δ=+0.233 · fixed={bench-aap2-001-single-job-outcome} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0001: rejected val=1.000 Δ=+0.233 -->
