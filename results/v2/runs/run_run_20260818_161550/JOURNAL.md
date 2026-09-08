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

## Iteration cand_0001 — fix wrong-controller-name cluster on task 004 (SKILL.md "Available Controllers" was fictional)

- Changes I made (1 line per edit; name the file/tool + cluster it targets):
  - SKILL.md → "Available Controllers": replaced fictional `east/west/event0/partner0` with the real fleet `prod0`, `prod1`; noted legacy names are unreliable. (cluster: task 004 wrong-controller-guess)
  - SKILL.md → new paragraph after controllers list: rule "when user gives a job ID but no controller, batch `get_job_log(prod0)` and `get_job_log(prod1)` in ONE turn; do not guess a single controller". (same cluster)
  - SKILL.md → new `<example>` block: worked example of the batched parallel call for the exact "job N failed, which task/host?" shape. (same cluster)
  - SKILL.md → new "Error interpretation" paragraph: `job not found` / `No simulation skill available` / HTTP 404 mean wrong controller, NOT tool unavailable; forbid the "I cannot access AAP2" abandonment on ONE error. (same cluster)
  - SKILL.md → Tips "Job ID typos are common" bullet: split into "user named a controller → ask user to double-check first" vs "user did NOT name one → do the parallel sweep, do not ask"; added a bullet on the failed-task-and-host output shape (`get_job_events failed_only=true` → report task+host). (same cluster)

- Per change, the EXPECTED effect + why each is safe:
  - Real controller list: agent will now call `prod0`/`prod1` when unspecified, so it can actually reach the job for task 004. Safe because all passing tasks (001/002/003/005/006/007/008/010) have the user explicitly name `prod0` or `prod1` — the agent passes those names through unchanged. Task 009 (user names `prod0`; sweeps after not-found) now sweeps `prod0`/`prod1` instead of legacy names; the "not found everywhere" conclusion is unchanged.
  - No-controller sweep rule: gated on "user does NOT name a controller", so it fires ONLY on task 004; every passing task in the trajectories has a controller in the user prompt.
  - Worked example: same gate as above; ignored on tasks where a controller is named.
  - Error-interpretation rule: prevents the "I cannot access AAP2" answer that scored 0.0 on task 004; passing tasks don't hit any per-controller error on their first call, so this path stays cold.
  - Tips split: narrows the existing "ask user to double-check" rule to the "user named a controller" case; the parallel-sweep branch is a new-case addition, not a loosening.

- Building on prior RESULTS: which prior entries' broke/fixed I used, and what I did NOT re-try because a prior RESULT showed it regressed (cite ids): none — this is iteration 1; LEDGER and RUNMAP are empty (seed baseline only).

- Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test): none yet.

- High-value clusters still NOT cracked (and the guard/tool designs already tried): none — task 004 is the only failing cluster. Sub-1.0 rewards on passing tasks (e.g. 001 at 0.53, 003/008/009 at 0.8) come from tool_calls=0.0 mismatch in the trajectory check; I did not chase those because a wrong guess about the "expected sequence" would regress the passing answer.

- Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch to): n/a — first iteration.

- Focus next iteration: if this iteration is REJECTED, read the framework's RESULT diff and identify which specific edit broke a passing task; if it is ACCEPTED, look at the tool_calls=0.0 signal on the passing tasks (001/003/008/009) to see whether a small nudge to prefer `get_job_events failed_only=true` right after `get_job_log` on failed jobs (already added as a Tips bullet, but could be pushed harder in the flow) could recover the trajectory-check points without changing the answer.

> **RESULT (framework, objective):** ACCEPTED (new champion) · val=0.719 Δ=+0.057 · fixed={—} · broke={bench-aap2-010-log-does-not-say}.
<!-- cand_0001: ACCEPTED val=0.719 Δ=+0.057 -->

## Iteration cand_0002 — (no handover written by the optimizer)

> **RESULT (framework, objective):** ACCEPTED (new champion) · val=0.750 Δ=+0.031 · fixed={bench-aap2-001-single-job-outcome, bench-aap2-003-never-started-explanation, bench-aap2-010-log-does-not-say} · broke={bench-aap2-002-failed-jobs-on-controller}.
<!-- cand_0002: ACCEPTED val=0.750 Δ=+0.031 -->
