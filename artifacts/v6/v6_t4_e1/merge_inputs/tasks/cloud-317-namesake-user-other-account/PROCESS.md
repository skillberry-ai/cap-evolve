# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got real evidence (the `trajectories/` files are stubs)

The 10 files in `./trajectories/` have `"trace": null` and `"tool_calls": []` — they
(`.../v6_2026-10-16/_run/jobs/v6_g2_e1/cloud-317-namesake-user-other-account/seed-*/`).
also holds re-runs) and scripted the analysis rather than eyeballing it. That is where
every number below comes from.

Task ground truth also available: `_run/tasks/bench-v6-.../provenance.md`,
`seeds/cloud.json`, `instruction.md`, and the simulator contract in
`parsec-cloud/SKILL.md`.


| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |

## Changes made this iteration

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE (replace, not append) | `security_agent.md` | "Key columns" → **"Supported columns — this list is exhaustive"** (6 entries). Explicit: any other name is unsupported, the failure is *silent*, and an unsupported column in the SELECT list is as damaging as in the WHERE clause. Plus a worked example with a placeholder account/user. Generalizes: states the store's actual contract, so any identity/period/account query benefits. | Yes — the 26 passing queries already used supported columns for filtering; this only removes decorative unmapped columns. |
| 4 | CONTRACT | `shared_context.md` | New "Answering Every Part of a Multi-Part Question": answer yes/no in a sentence not just a table cell; state absences as negated actions in prose; give the count next to the user's noun and make it equal the rows you actually attribute; report a verified absence confidently. Domain-general (output contract) → correctly placed in `shared_context.md`. | Yes — additive to formatting; passing answers already satisfy it. |
| 5 | KNOWLEDGE (narrow, not loosen) | `security_agent.md` | `lookup_events` is "last few hours only", **not** a substitute when the user names a past window; its `filters` match event attributes, so never pass a username/account/ARN as `event_name`. | Yes — narrows a preference that was over-broad; recent-activity use is unchanged. |

Also reconciled a leftover conflict: the SQL-syntax line said `WHERE eventTime >` while
the new worked example uses inclusive bounds. It now says to bound inclusively when the

## Verify-the-fix (one line per change: the trace it targets → what it now does)

  **all 10 zero-row queries referenced at least one unsupported column; 0 did not.**
  `errorCode`, `errorMessage`. Its 3rd query had already dropped *both* identity filters
  and scanned the whole account for 4 days and still returned 0 — a widen-only rule could
  never have recovered it, but the column rule removes the one condition every zero-row
  query shared. Honest limit: only **1** observed query referenced exclusively supported
  columns (it returned rows), so this is a strong *necessary*-condition result, not a
  proven sufficient one.
- **Cluster 2.** At the exact failure point the agent said "account is not enrolled in
  CloudTrail Lake" after 3 filtered queries. The new rule forbids that claim without an
  empty time-only probe, and step 1 sends it back to rewrite the columns — the probe it
  never ran.
  account), so this edit is insurance against the task's designed trap rather than a
  and hits a forbidden fact.
  "Delete operations: **None.**" as a table label. The new rule explicitly requires the
  negated verb in prose ("none of these calls deleted anything"), which matches the
  `lookup_events {filters:{event_name:"nightly-ingest"}}` — a username in an event-name
  field. The new text names exactly this misuse and rules out the pivot for a named
  historical window.

## Escalation (no prose fix exists)

`query_aws_account list_users` **timed out on both attempts** (240 s each). The agent
behaved correctly: it retried once, then reported the gap honestly instead of fabricating.
No prompt edit can recover a tool timeout — this is infrastructure flakiness and a

## Process & features used

- Subagents / worktrees / parallel features used (or: "serial fallback because …"):
  **Serial, scripted analysis rather than a subagent fan-out.** The whole focus set is
  *one task*, and the decisive work was quantitative (correlating 37 query shapes against
  single transcript set and could not have produced the column/zero-row correlation that
  drove every edit. Fan-out is the right tool for many clusters across many tasks; here
  it would have been ceremony.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: none — this is

## Good things to PRESERVE (do not let a future iteration undo these)

- The exhaustive six-column list in `security_agent.md`, and the statement that an
  unsupported column is harmful **in the SELECT list too**. That is the non-obvious,
  evidence-backed core of this iteration; a future edit that re-adds `userIdentity.arn`
  to a "key columns" list would reintroduce the primary failure.
- "Empty result ≠ no data" and the ban on asserting an infrastructure gap from filtered
  queries.
- `userIdentity.username` equality over any `LIKE`-on-ARN formulation.

## Deliberately skipped (cluster + why)

- Any rule keyed to this task's literals. No account id, username, key id, event name,
  window, or count from this task appears in any edit; the worked example uses an
  invented placeholder account and user.
