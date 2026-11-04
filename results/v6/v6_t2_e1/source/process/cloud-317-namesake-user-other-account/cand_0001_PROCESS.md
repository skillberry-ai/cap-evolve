# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got real evidence (the `trajectories/` files are stubs)

The 10 files in `./trajectories/` have `"trace": null` and `"tool_calls": []` — they
carry only the scalar reward. The actual transcripts are reachable via
`rollout.metadata.trial_dir`, which points into the parsec bench run tree
(`.../v6_2026-10-16/_run/jobs/v6_g2_e1/cloud-317-namesake-user-other-account/seed-*/`).
Each trial dir holds `agent/agent.jsonl` (full tool calls + results + final answer) and
`verifier/reward-detail.json` (exactly which contract item was missed). I read **37
query_cloudtrail calls across 37 trial dirs** (more than the 10 val trials — the tree
also holds re-runs) and scripted the analysis rather than eyeballing it. That is where
every number below comes from.

Task ground truth also available: `_run/tasks/bench-v6-.../provenance.md`,
`seeds/cloud.json`, `instruction.md`, and the simulator contract in
`parsec-cloud/SKILL.md`.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Silent empty CloudTrail result from an unsupported column** | cloud-317 (drives the 0.533 trial; 10/37 queries) | The store maps only 6 columns (`eventTime`, `eventName`, `eventSource`, `eventID`, `recipientAccountId`, `userIdentity.username`). `security_agent.md` advertised `userIdentity.arn`, `awsRegion`, `requestParameters`, `errorCode`… as "key columns". Referencing an unmapped column **anywhere — SELECT list included** — can return 0 rows with `bytes_scanned: 0` and no error. | KNOWLEDGE | rewrite the column reference as an exhaustive supported-list + worked example |
| 2 | **Zero rows misdiagnosed as "account not enrolled"** | cloud-317 (the 0.533 trial) | The old rule was "empty results → widen the time window". The agent obeyed it, widened to 4 days, still got 0 (same unmapped column), and concluded the account was absent from CloudTrail Lake — then reported a non-existent infrastructure gap. Widening never tests the predicate that was actually wrong. | BEHAVIORAL | replace widen-first with a predicate-elimination ladder + ban the "no data" claim unless a time-only probe is empty |
| 3 | **Namesake principal across accounts (the task's actual trap)** | cloud-317 (latent in all passing trials) | An IAM username is unique only within an account; the org-wide store holds a same-named user in another account with 3 `Delete*` events. A username-only filter returns 7 rows and attributes deletions to the wrong principal. Old text said "always filter by `recipientAccountId`" as a *performance* tip, never as a correctness/attribution rule. | KNOWLEDGE | add a scope-the-principal rule: filter + SELECT + verify the scope column, attribute out-of-scope rows explicitly |
| 4 | **Absence/yes-no answered only in a table cell** | cloud-317 (the 0.922 trial) | Agent wrote "Delete operations: **None.**" as a label. The contract wants the conclusion as a negated-verb sentence. Nothing in the prompt said to state a verified negative in prose. | BEHAVIORAL | add a multi-part/absence answer contract to `shared_context.md` |
| 5 | **`lookup_events` used for an explicit historical window** | cloud-317 (the 0.533 trial's last call) | Prompt said "**prefer** `lookup_events` over `query_cloudtrail` for single-account investigations" unconditionally. That action only covers the last few hours and cannot filter a named past window. The agent pivoted to it and passed the *username* as `event_name` → 0 events, reinforcing the wrong conclusion. | KNOWLEDGE | narrow the preference with the window condition + a don't-misuse-filters note |

## Changes made this iteration

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | KNOWLEDGE (replace, not append) | `security_agent.md` | "Key columns" → **"Supported columns — this list is exhaustive"** (6 entries). Explicit: any other name is unsupported, the failure is *silent*, and an unsupported column in the SELECT list is as damaging as in the WHERE clause. Plus a worked example with a placeholder account/user. Generalizes: states the store's actual contract, so any identity/period/account query benefits. | Yes — the 26 passing queries already used supported columns for filtering; this only removes decorative unmapped columns. |
| 2 | BEHAVIORAL | `security_agent.md` | Replaced "empty results → widen immediately" with a 4-step elimination ladder (fix columns → drop identity → drop account → time-only), plus: never claim "not enrolled / no data" unless the time-only probe is empty, because `bytes_scanned: 0` means *your predicates matched nothing*. Generalizes to any filtered store where absence is ambiguous. | Yes — fires only after a 0-row result. |
| 3 | KNOWLEDGE | `security_agent.md` | New "an IAM user name is only unique within one account" rule: put the scope in WHERE, **also SELECT the scope column and verify every reported row**, exclude out-of-scope rows from the count, attribute them to the other account in the same sentence, and cross-check against known IAM creation time. Written for "account, project, subscription, or cluster" — any tenant-scoped name in a multi-tenant store. | Yes — reinforces what passing trials already did implicitly. |
| 4 | CONTRACT | `shared_context.md` | New "Answering Every Part of a Multi-Part Question": answer yes/no in a sentence not just a table cell; state absences as negated actions in prose; give the count next to the user's noun and make it equal the rows you actually attribute; report a verified absence confidently. Domain-general (output contract) → correctly placed in `shared_context.md`. | Yes — additive to formatting; passing answers already satisfy it. |
| 5 | KNOWLEDGE (narrow, not loosen) | `security_agent.md` | `lookup_events` is "last few hours only", **not** a substitute when the user names a past window; its `filters` match event attributes, so never pass a username/account/ARN as `event_name`. | Yes — narrows a preference that was over-broad; recent-activity use is unchanged. |

Also reconciled a leftover conflict: the SQL-syntax line said `WHERE eventTime >` while
the new worked example uses inclusive bounds. It now says to bound inclusively when the
user gives both endpoints (the 0.922 trial used `>=`/`<`).

## Verify-the-fix (one line per change: the trace it targets → what it now does)

- **Cluster 1 / the 0.533 trial.** Scripted check over all 37 queries:
  **all 10 zero-row queries referenced at least one unsupported column; 0 did not.**
  The failing trial's three queries referenced `userIdentity.arn`, `awsRegion`,
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
- **Cluster 3.** Latent in this bundle's trials (all that got rows had already scoped by
  account), so this edit is insurance against the task's designed trap rather than a
  repair of an observed miss. `provenance.md` confirms an unscoped answer scores 0.767
  and hits a forbidden fact.
- **Cluster 4 / the 0.922 trial.** It missed only `no-deletes`, having written
  "Delete operations: **None.**" as a table label. The new rule explicitly requires the
  negated verb in prose ("none of these calls deleted anything"), which matches the
  contract's accepted forms.
- **Cluster 5.** The failing trial's final call was
  `lookup_events {filters:{event_name:"nightly-ingest"}}` — a username in an event-name
  field. The new text names exactly this misuse and rules out the pivot for a named
  historical window.

## Escalation (no prose fix exists)

One trial (0.844) missed `created-time` + `active-key` purely because
`query_aws_account list_users` **timed out on both attempts** (240 s each). The agent
behaved correctly: it retried once, then reported the gap honestly instead of fabricating.
No prompt edit can recover a tool timeout — this is infrastructure flakiness and a
floor on this task's achievable mean reward. Worth raising with the harness owners.

## Process & features used

- Subagents / worktrees / parallel features used (or: "serial fallback because …"):
  **Serial, scripted analysis rather than a subagent fan-out.** The whole focus set is
  *one task*, and the decisive work was quantitative (correlating 37 query shapes against
  rewards across trial dirs). Parallel diagnosis subagents would have re-read the same
  single transcript set and could not have produced the column/zero-row correlation that
  drove every edit. Fan-out is the right tool for many clusters across many tasks; here
  it would have been ceremony.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: none — this is
  iteration 1; `RUNMAP.md`, `LEDGER.md` and `rejected.jsonl` are all empty.

## Good things to PRESERVE (do not let a future iteration undo these)

- The exhaustive six-column list in `security_agent.md`, and the statement that an
  unsupported column is harmful **in the SELECT list too**. That is the non-obvious,
  evidence-backed core of this iteration; a future edit that re-adds `userIdentity.arn`
  to a "key columns" list would reintroduce the primary failure.
- "Empty result ≠ no data" and the ban on asserting an infrastructure gap from filtered
  queries.
- `userIdentity.username` equality over any `LIKE`-on-ARN formulation.

## Deliberately skipped (cluster + why)

- The `list_users` timeout (0.844 trial) — infra flakiness, see escalation above.
- Any rule keyed to this task's literals. No account id, username, key id, event name,
  window, or count from this task appears in any edit; the worked example uses an
  invented placeholder account and user.
