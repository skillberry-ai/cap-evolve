# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1/1. Parent = seed (val 0.830: 19 solid / 48 flaky / 0 failing of 67).
No prior iterations existed (LEDGER/RUNMAP/INSIGHTS/rejected.jsonl all empty), so
nothing to build on or avoid re-testing.

## 0. THE FINDING THAT REDIRECTED THIS ITERATION — read this first

**53 of the 67 val tasks never read `orchestrator.md`.**

`classify_fast()` (`_run/parsec-live/src/agent/agents.py:256`) is a regex classifier
run *before* the orchestrator LLM. On a match, `orchestrator.py:1202` calls
`run_sub_agent_streaming(...)` then `return`s — the orchestrator prompt is never
built. I verified both call sites by reading them, then ran `classify_fast` over all
67 `instruction.md` files: **53 fast-pathed, 14 orchestrator-routed.** 10 of the 11
worst-scoring tasks are fast-pathed.

Consequences I planned around:
- A fast-pathed sub-agent reads `shared_context.md` + its own domain file only. So
  **`shared_context.md` is the highest-leverage file in the edit space** and
  `orchestrator.md` is nearly dead weight. I spent the budget accordingly
  (+225 lines shared vs +27 orchestrator) — the opposite of what the file names suggest.
- A large real cluster is **unreachable by any prompt edit**: the matched agent
  often lacks the tool the task needs (see "Deliberately skipped" and
  FRAMEWORK_IMPROVEMENTS.md). ~3.4 task-points.

Also: many tasks the brief calls "flaky" have **zero variance** over 10 trials
(platform-071 all 0.383, platform-121 all 0.500, cloud-058 all 0.600, cost-407 all
0.600). Those are systematic misses, not noise, and I prioritised them.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 0 | **Fast-path routes to an agent lacking the required tool** (~3.4 lost) | cloud-304, cloud-315, platform-071, icinga-013, cloud-074, cloud-310 (+tool_calls of cost-410/419) | regex classifier picks an agent by topic word; that agent has no such tool and cannot hand off | CAPABILITY-GAP (code) | **NOT in edit space** — escalated; wrote only the generalisable half of the rules |
| 1 | Directory path fetched as a file → search thrash → rounds exhausted → non-answer (~1.2) | platform-121, 032, 007, 137, 104 | prompt says `fetch_github_file` fetches "files and directories"; it errors on dirs | BEHAVIORAL (prompt was *false*) | correct the false statement + path-shape rule + stop rule |
| 2 | Epoch seconds converted by eye → wrong date/hour (~1.1) | icinga-215, 204, 206, 216, 212 | no epoch-conversion guidance anywhere; mental conversion slips days/months | KNOWLEDGE | add anchor table + arithmetic + worked example |
| 3 | Result's own scope / period / placeholder / absent field ignored (~1.1) | cost-407, 408, 418, 402, 051 | nothing tells the agent to read a result's self-describing fields before using its numbers | KNOWLEDGE | sharpen Tool Result Handling + tool-specific semantics |
| 4 | Refuse or ask instead of running the feasible read (~0.9) | cloud-057, 058 | mixed/odd-input requests answered with 0 tool calls | DECISION/PERMISSION | explicit do-the-reads-then-decline rule |
| 5 | Wrong AAP2 job action; failed-events read skipped (~0.5) | platform-126, 116, 004 | prompt says "**Always use `get_job_log` instead of `get_job`**"; `get_job_events` buried in a GUID-only flow | DECISION (prompt was *causal*) | delete the ban, add an action-selection rule |
| 6 | Answer-surface defects hide correct facts (~0.5) | icinga-045, 204, 201, 212; platform-116, 101, 153 | emoji between name and state, question-shaped headings, `5,320` commas, markup inside a phrase | BEHAVIORAL | output-form rules at top of shared file |
| 7 | Lifecycle cost split estimated; verdict hedged (~0.3) | cost-419, 410 | no rule for splitting a daily series at a boundary; conditional go/no-go | KNOWLEDGE | boundary + exact-sum + unconditional-verdict rule |
| 8 | Line asked for, number never given or miscounted (~0.3) | platform-152, 153, 136, 101 | `content` has no line numbers; no citation rule | KNOWLEDGE | mechanical counting rule |
| 9 | `userIdentity.arn` null → caller reported unknown (~0.2) | cloud-057, 317 | key-column list omits the lowercase `username` column | KNOWLEDGE | add the column + null fallback |
| 10 | `command_endpoint` ≠ host not followed through (~0.17) | icinga-222 | field absent from the extract list | KNOWLEDGE | add field + the follow-up call |
| 11 | Region guessed; empty result read as a negative finding (~0.15) | platform-158 | prompt sends it to CloudTrail for regions instead of the provisioning record | KNOWLEDGE | region-from-record + scope-of-absence rule |
| 12 | Splunk `controller` given the full hostname (~0.12) | platform-112, 155 | prompt says to use the hostname / `cluster_host_id` | KNOWLEDGE (prompt was *false*) | correct to short name |
| 13 | DNS negative caching unknown (~0.1) | platform-148 | domain fact absent | KNOWLEDGE | failure-pattern table row |

Three clusters (1, 5, 12) are cases where **the baseline prompt asserted something
false and was itself the cause**. Those are corrections/deletions — the
highest-confidence edits available, and unreachable by adding prose.

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 6 | rewrite rule, positively framed | `shared_context.md` | answer each question in one plain sentence before any table; state an entity's status as the bare word right after its name (no icon between); headings assert findings, not questions. Pattern = "the fact is present but unreadable", not any task's words | emoji removal only makes passing icinga answers easier to match; verified their graded items are digits/words |
| 4 | add sourced rule + narrow a decision | `shared_context.md` (Security) | run every read step, then state in one sentence which step you did not perform and that your tools are read-only; never offer a read you can already run; when advising *against* an action don't describe how to do it | last clause added *because* the first draft tripped platform-118's forbidden item |
| 9 (ident) | add rule | `shared_context.md` | query by the most specific id you already hold; pass a wrong-format identifier through unchanged (never repair) and name what you could not retrieve | documented normalisations (e.g. `sandbox-` strip) explicitly preserved |
| 7 | add rule | `shared_context.md` (Account Pooling) | boundary from the lifecycle record or the gap in the series; sum exact daily entries (never rate × days); unconditional verdict when spend contradicts a teardown | sits beside the existing attribution-by-window rule it extends |
| 3 | tighten + add rule | `shared_context.md` (Tool Result Handling) | read a result's scope label / covered period / unasked-for fields / absent fields / staleness before using its numbers; a failed input is not a zero; don't combine figures over mismatched extents; a numeric filter drops rows lacking the field; an empty result is only evidence about the scope you chose | carve-outs protect cost-073 (item-key grouping), platform-041 (entity comparison), icinga-214 (staleness), platform-062 (absence-is-a-finding) |
| 1 | correct a false rule + add rule | `shared_context.md`, `babylon_agent.md`, `aap2_agent.md` | `fetch_github_file` is for one file; decide by path shape (dir → `<path>/<file>` or `common.yaml`); a `/runner/project/<path>:<N>` log line is a repo-relative path; pin the known revision; search before guessing; an empty search is not proof of absence; stop and answer when you already hold the values | stop rule narrowed to *same tool, same target, no other source left* so platform-062's broadening still happens |
| 8 | add rule + example | `shared_context.md` | cite a line by NUMBER; count mechanically from line 1 of `content`; cite the declaring line, not a nested property line | generic `some_key: value-a` example; no passing task has a line requirement |
| 6 (numbers) | add rule | `shared_context.md` | non-currency quantities as bare digits (no thousands separator); compute margins from raw values; sum exact rows; refute the user's proposed cause but don't volunteer your own hypotheses | currency exempted so cost-028/073/416 keep `$12,400`; last clause rewritten to protect platform-118/067 refutations |
| 2 | add rule + worked example | `icinga_agent.md` | month-anchor table + div/mod arithmetic + one worked example; "now" is whatever the user says it is | **moved out of** `shared_context.md` after confirming no non-icinga task has epochs in tool results — correct blast radius, 50+ tasks don't pay the tokens |
| 10 | add rule | `icinga_agent.md` | `command_endpoint`/`check_source` ≠ `host_name` ⇒ the check ran elsewhere; query that machine's services (`get_services`, not `get_hosts`) and say the monitored host isn't measured | fires only when they differ; no passing task has that |
| 3 | add tool semantics | `cost_agent.md` | aggregate-labelled row: read the entity from the row's item key first, else treat as org total; a preset's zeros for metrics it never requested are placeholders ("not measured"), not a data gap; response `period` may be clamped; GCP figures are net of credits with no itemised field | item-key clause added *because* the first draft was factually wrong for cost-073's seed |
| 5 | delete a causal rule + add decision rule | `aap2_agent.md`, `babylon_agent.md` | removed "Always use `get_job_log` instead of `get_job`"; added: `get_job` for timing/outcome, `get_job_log` for log text, `get_job_events failed_only` for every failed job (role/host come from the event row, never inferred from env_type) | contracts match by subset, so an extra leading `get_job` is ignored; platform-062 already makes both calls |
| 12 | correct a false rule | `aap2_agent.md` | `search_aap2_logs` takes the controller's SHORT name, not the hostname/`cluster_host_id` | no other contract pins a Splunk controller |
| 13 | add rule | `aap2_agent.md` | negative-caching row: negative TTL = min(SOA record TTL, SOA minimum field) | new table row only |
| 9 | add rule | `security_agent.md` | `userIdentity.username` (lowercase) is the reliable caller column; re-run with it before reporting the caller unknown | additive column knowledge |
| 0/3 | tighten rule | `security_agent.md` | an agreement is in force per `agreement_end` + `auto_renew` vs the user's as-of date, never `status` alone; cite `last_updated` as the staleness evidence; quote the stored status but never assert it; scope the query by account | generalises the stale-status pattern even though its visible task is unreachable |
| 11 | correct a misleading rule | `security_agent.md` | region comes from the provisioning record, not a CloudTrail hunt or a sweep; an empty result in one region is not "nothing was launched" | only changes behaviour when the region is unknown |
| 0/11 | tighten routing | `orchestrator.md` | route by the data source each step must read, not topic words; resolve an identifier in its own domain first and pass the resolved values on; finish a step a sub-agent could not run before offering follow-ups | only 14 tasks read this file; kept minimal for that reason |

## Verify-the-fix
- **Cluster 2 / icinga-204, 206, 216:** tool returned `end_time 1794952800`; agent wrote "2026-11-17 06:00"/"11-16 10:00". Table anchors Nov-2026 = 1793491200; arithmetic yields 2026-11-17 22:00 and elapsed 11.5 h — the graded values. **WOULD FIX.** icinga-215/212: fixes the date/time items; each has a *separate* second miss (a forbidden phrase; an unmatched "only on main" form) that I did not chase. **PARTIAL.**
- **Cluster 3 / cost-407:** the single row was `{"account_id": "org-wide", …, "total": 61842.55}` and the agent printed it as the account's total. New rule: look for the entity in the row's item key (service-grouped here, so none), then report under the aggregate label and say there is no per-account figure. **WOULD FIX.** cost-402 (placeholder zeros called "a data gap in the cache") and cost-051 ("no credit line items") **WOULD FIX**; cost-418's ratio **WOULD FIX**; cost-408 **PARTIAL** (its forbidden heading is cluster 6, not 3).
- **Cluster 1 / platform-121:** all 10 trials fetched the bare directory from a `similar_items` row, then burned every remaining round on empty searches and ended with "I've used all my planned tool calls". Path-shape rule produces `<path>/common.yaml` — the exact unmatched expected call. **WOULD FIX.** platform-007 (forbidden directory fetch in 5 trials, missing `search_github_repo` in the other 5) **WOULD FIX**; platform-137 **WOULD FIX** (the exact path is in the log); platform-032 **PARTIAL**; platform-104 **~0** on the line item.
- **Cluster 4 / cloud-057:** 8/10 trials made zero tool calls, two of them literally "I'll run the count/attribution query now. Just confirm." The "never offer a read you can already run" clause targets that sentence. **WOULD FIX.** cloud-058: 10/10 zero calls; rule forces one call with the id as given plus an explicit "could not retrieve" sentence. **WOULD FIX.**
- **Cluster 5 / platform-126, 116:** expected `get_job` unmatched in 9/10 and 10/10; the ban was the cause and is deleted. platform-004: `get_job_events failed_only` skipped in 9/10, so the failing `role` was invented from the env_type; the one trial that called it scored 1.0. **WOULD FIX** all three.
- **Cluster 12 / platform-112:** all 10 trials passed the FQDN; seeded rows carry the short name, so every call returned `[]`. **WOULD FIX.** platform-155 **PARTIAL** (one trial never called Splunk).
- **Cluster 10 / icinga-222:** result showed `command_endpoint: <other machine>`; 9/10 trials never called `get_services` on it. Rule prescribes that exact call. **WOULD FIX.**
- **Cluster 9 / cloud-057:** trials selected `arn`/`userName` (camelCase), both null, then reported the caller "not captured"; only the lowercase column is mapped. **WOULD FIX.**
- **Cluster 6 / platform-116:** `5,320s` fails the count matcher's digit-boundary guard; a reviewer confirmed with `verify.py` that removing the comma raises 6/10 trials, and that the rule's "no task failed" phrasing does *not* trip the forbidden item. **WOULD FIX.**
- **Cluster 11 / platform-158:** **PARTIAL and high-variance.** The security agent has no `query_aap2`, so the region can only arrive via the orchestrator's new resolve-first rule — an LLM routing decision. The security-side rule alone only prevents the false "no instances" claim.
- **Cluster 0:** **WOULD NOT FIX.** No prompt supplies a missing tool; the required facts are unreachable. Listed under skipped.

## Process & features used
- **6 parallel read-only diagnosis subagents** (5 by domain group + 1 cross-domain
  mechanism sweep) over a digest I built joining, per task × 10 trials, the
  instruction, the author's `provenance.md`, `verifier/reward-detail.json` (actual
  calls, `unmatched_expected`, every missed rubric id) and `agent/agent.jsonl`.
- I **independently verified every load-bearing claim** before editing: recomputed
  all 36 epoch anchors, grepped the harmful prompt lines, tallied zero-tool-call
  trials, and read both `classify_fast` call sites. Four subagents re-derived the
  routing finding from different domains, which is why I trusted it enough to
  re-plan around it.
- Edits made directly rather than in per-issue worktrees: the fixes are surgical and
  several touch overlapping regions of `shared_context.md`, so merging would have
  added conflict risk for no parallelism gain.
- **2 parallel review subagents** (adversarial regression hunt + per-fix
  verify-the-fix) then **1 final pre-ship check**. 13 + 7 defects found and fixed;
  two were settled by the reviewers *executing the target task's own `verify.py`*
  rather than reasoning about it.
- Prior iterations read: none exist. `RUNMAP.md`, `LEDGER.md`, `INSIGHTS.md` and
  `rejected.jsonl` were all empty — this is the first iteration of the run.

## Good things to PRESERVE (do not let a future iteration undo these)
- **The three corrections of false baseline statements.** Re-adding "Always use
  `get_job_log` instead of `get_job`" re-breaks platform-126 and -116; re-adding
  "`fetch_github_file` — Fetch files and directories" re-breaks platform-121/007;
  re-adding the Splunk hostname instruction re-breaks platform-112.
- **The epoch section lives in `icinga_agent.md`, not `shared_context.md`.** Moving
  it back makes 50+ tasks pay for a rule only icinga needs.
- **Every carve-out listed in "protects passing?"** — each one protects a *named*
  passing task that my own first draft broke: cost-073 (item-key), platform-041
  (entity comparison), platform-062 (broadening after an empty result, and
  absence-as-finding), platform-118 (don't say how someone else could do it;
  do refute the user's proposed cause), platform-018 (no generic exclusive-end
  claim), icinga-214 (staleness needs an event date in the same record). Do not
  re-broaden these rules.
- **Neutral example values.** The first draft's examples were lifted from graded
  answers; they were all replaced. Re-introducing a graded value as an example is
  the exact failure mode this round is testing for.

## Deliberately skipped (cluster + why)
- **Cluster 0, the routing fast-path (~3.4 task-points — the largest in the run).**
  Needs a code change (check patterns in priority order, fall through to the
  orchestrator on a multi-domain match, or let sub-agents hand off). Out of this
  phase's edit space; escalated in FRAMEWORK_IMPROVEMENTS.md. I did write the
  *generalisable* half of those rules (stale status, filter-drops-rows) so they can
  pay off on held-out tasks that reach the right agent.
- **icinga-215's forbidden `no-expiry` and cost-408's forbidden heading.**
  Recoverable only by prescribing phrasings that satisfy a matcher. That is
  grader-gaming, would not transfer to the hidden set, and I left it.
- **platform-104's line number.** Its graded line is a block start; the rule now
  matches that, but Sonnet's line counting stays unreliable. Expected ~0.
- **`ocpv_agent.md` — untouched.** No OCPV task scores below 0.986.
- **platform-005/117/119/134/139/165.** Single-trial dips, no mechanism found;
  per LEDGER guidance a sub-2·SE move is not evidence of anything.

## Risks I am shipping knowingly
1. `shared_context.md` more than doubled (237 → 491 lines) and is prepended to every
   sub-agent. I cut the worst value-per-line passage (moved epochs to icinga) but
   the rest stays. If this candidate is rejected with no clear per-task cause,
   **attention dilution is the first hypothesis** — split the remaining rules into
   domain files rather than rewriting them.
2. The epoch and line-counting rules require arithmetic/counting the reader does
   imperfectly. They should raise the mean but may add variance.
3. Clusters 9/10/11/13 are single-task hypotheses. Each is a documented tool or
   protocol fact rather than an inference from one trace, but they are the weakest
   items here.

---

# DIAGNOSIS.json
Written to `./DIAGNOSIS.json` alongside this file.
