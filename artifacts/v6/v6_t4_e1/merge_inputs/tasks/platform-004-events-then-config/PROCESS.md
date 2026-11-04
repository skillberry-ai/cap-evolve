# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got the ground truth (do this first, future iterations)


- Task def + rubric: `/dccstor/.../rhdp-parsec/v6_2026-10-16/bench-v6-harbor-tasks/bench-v6-platform-004-events-then-config/`
  (`instruction.md`, `tests/expected.json`, `golden.json`, `seeds/platform.json`)
- Transcripts: `/dccstor/.../_run/jobs/v6_g2_e1/platform-004-events-then-config/seed-N/<ts>/<id>/agent/agent.jsonl`

Prompt footprint: `services = ["platform","github"]`; the orchestrator routes job
failures to `investigate_aap2_job` → `orchestrator.md` + `shared_context.md` +
not edited.

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A | BEHAVIORAL (narrow an over-broad rule) | `aap2_agent.md` rules #3/#4 | "Enough data" = every field the user asked for is in a tool result; "don't re-fetch" forbids repeating the **same `action`**, explicitly not a *different* one. Generalizes: any multi-action tool where actions return disjoint fields. | Yes — budgeting still bars speculative browsing; only field-bearing calls are exempted |
| A | KNOWLEDGE + worked example | `aap2_agent.md` (new section) | Field table for `get_job_log` vs `get_job_events`; MUST-call rule **scoped to fields the log does not reliably carry**; ban on deriving a role from a path/config/play/task name; 3-step worked example. Generalizes: rendered output vs structured rows is a universal distinction. | Yes — trigger is scoped so it does not fire on task/host/error alone |
| A | BEHAVIORAL (fix the decision point) | `aap2_agent.md` Step 1 | Step 1 of "Investigate AAP2 Job Failures" now **requires** the `get_job_events` + `failed_only=true` call for any failed job. This is the procedure the agent actually executes. | Yes — restores the seed's own rule (seed line 61) that lost to rules #3/#4; skipped for non-failed jobs |
| B | BEHAVIORAL | `aap2_agent.md` (new section) | Retry an identical failing call at most once; then fall back to a different `action` that carries an owed field; report which fields were recovered and name only the specific ones missing. Generalizes: any partial-outage situation with overlapping data sources. | Yes — bounded to fields still owed, so no extra calls when nothing is missing |
| A | BEHAVIORAL (narrow overconfidence) | `aap2_agent.md` report template | `{role}` must be copied from an event row or a literal `TASK [role : task]` prefix; otherwise write `role not retrieved`. Host slot = the host that actually failed, not the first in the recap. | Yes — only constrains a slot that was previously guessed |
| C | KNOWLEDGE | `aap2_agent.md` Step 6 | Corrected the v2 owner; derive `owner` from the project URL in the tool result, never memory; a user-supplied `owner/repo` overrides any table. | Yes — removes a forbidden-call landmine |
| A+B | KNOWLEDGE (domain-general) | `shared_context.md` "Answer Every Field That Was Asked" | Enumerate the fields the request names and pair each with its tool result before answering; make the targeted call for a missing one; never satisfy a field with a similar-looking inferred string. Genuinely cross-domain (multi-part requests exist in every domain), hence shared. | Bounded: targeted calls for *named* fields only; explicitly not broad re-querying |
| A+B | contradiction fix | `shared_context.md` | "NEVER same params twice" now exempts **one** retry of a call that failed *without returning data*; "don't re-fetch" scoped to the same field/action so it no longer blocks a complementary action. | Yes — resolves a conflict with the new timeout rule |
| A+C | overfit cleanup (pre-existing text) | `shared_context.md` Sources example | The example URL used the **forbidden** wrong-owner repo *and* this task's exact config path — both priming the two failure modes. Replaced with `{owner}/{repo}/{ref}/{config}` placeholders. | Yes — removes task-specific priming from a shared file |

## Verify-the-fix
- **Cluster A, exact decision point** (`get_job_log` returned and fully explains the failure; call events or not?): in the seed, three texts said stop/redundant and procedural Step 1 listed only the log. Now Step 1 itself requires the call; rule #4 no longer calls a different `action` redundant; rule #3's "enough data" no longer covers a named field; the output-format "STOP calling tools" line is scoped to exploratory fetches. The Step 1 edit is the one most likely to flip behavior because it sits in the procedure being executed, not in a tips section.
- **Cluster A, second line of defence**: if the call is still skipped, the field table + report-template rule make the agent write `role not retrieved` instead of the config name. That does not recover the point — it only prevents a wrong assertion — which is precisely why the Step 1 edit carries the fix.
- **Cluster B, exact point** (after the second identical timeout): the agent is now told to try the sibling action, which returns the task and host it previously declared unavailable, and to name only the genuinely missing field.

## Process & features used
- **The adversarial reviews changed the candidate materially.** Review 1 found that my first pass had missed the real decision point (Step 1 still named only `get_job_log`), surfaced 4 surviving contradictions, and flagged 4 overfitting risks in my own added text. Review 2 confirmed the fixes and caught a stale "fields that are never printed in the log" phrase that contradicted my own corrected table. Both rounds are reflected above.

## Non-overfitting audit
The final diff contains **no** instance-specific literal — no role name, job id, hostname,
controller name, GUID, config path, or variable name. Each rule restates as a pattern:
*"the structured-event action carries fields the rendered log does not"*, *"never
synthesize an identifier from a similar-looking string in a different namespace"*,
*"answer every field that was asked"*. I also removed two **pre-existing** task-specific
strings from the shared Sources example, since they were priming both failure modes.
A correction flagged in review: I initially claimed the role is "never" in the log —
true of this fixture but false of real Ansible, which prints `TASK [role : task]`. The
table now says "only if the log prints a `TASK [role : task]` prefix", which is correct
in general and still routes this fixture's prefix-less line to the events call.

## Good things to PRESERVE (do not let a future iteration undo these)
- **Step 1's required `get_job_events` call** — the only edit placed in the procedure the agent actually executes. If anything is reverted, not this.
- **Scoping of the MUST-call trigger** to fields the log does not reliably carry. Broadening it to task/host/error would fire on nearly every investigation and inflate tool calls.

## Deliberately skipped
- **No new tool needed / no capability escalation.** `get_job_events` with `failed_only` already exists and already returns the role; the seed prompt was talking the agent out of using it. This is a genuine prompt-layer fix, not a disguised code gap.
