# icinga-010-stuck-anarchysubjects

<!-- BEGIN:auto -->

**task:** `icinga-010-stuck-anarchysubjects`  
**category:** icinga  
**tranche:** regression  
**services:** icinga, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.495 |
| our baseline (v4_t1_e1) | test | 3 | 0.402 |
| seed (val, v4_t2_e1) | val | 5 | 0.467 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.495 |
| cand_0002 (val, v4_t2_e1) | val | 5 | 0.495 |
| final (test, v4_t2_e1) | test | 5 | 0.495 |

delta vs JB: 0.000 · delta vs our baseline: 0.093

**T2 cost/time:** $28.12, 1,477,226 tokens, 1.59h (eval $4.08/1,243,007tok · optimizer $24.05/234,219tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/report.md`, `.capevolve/v4_t2_e1_icinga-010-stuck-anarchysubjects/run_20260919_185334/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An Icinga alert reports AnarchySubjects stuck on a host. The task is to check the service's state and any suppression (comments or downtimes), then read the actual check script on GitHub to learn its configured critical threshold and report by how much the current value exceeds it -- grounding the verdict in configuration rather than the alert's own wording.

## What the optimizer tried

Two candidates against `orchestrator.md`, `shared_context.md`, `icinga_agent.md`, and `babylon_agent.md`. `cand_0001` initially diagnosed a missing Icinga entry in `orchestrator.md`'s Routing Guidelines (the alert's Babylon-sounding hostname routes it to the wrong domain agent) and added routing, suppression-reporting, and threshold-reporting rules — then, mid-iteration, found via direct code inspection that `orchestrator.md` and `icinga_agent.md` are never loaded for this task at all: a regex fast-path (`classify_fast`) dispatches straight to the Babylon agent before the orchestrator prompt is ever read. It pivoted to editing `babylon_agent.md` instead, adding a defer-guard against substituting a live measurement for the monitoring value the alert actually asked about. `cand_0002` made three further edits to `icinga_agent.md` (an explicit call-order table, a conditional step, and a consolidated "start from the user's location" rule) while stating up front that these are unmeasurable — `icinga_agent.md` contributes 0 characters to this task's prompt.

## Why the winning candidate won

JOURNAL.md derives the task's exact reward ceiling from the grader's own arithmetic: with the routing bug locking out all three `query_icinga` calls (`tool_calls` stuck at 0.25) and two of five answer items structurally unreachable, `0.3·0.25 + 0.7·(3/5) = 0.495` is the maximum honest score — identical to `cand_0001`'s measured val and to every individual trial's reward, with zero cross-trial variance. `cand_0001` was accepted (val 0.495, Δ +0.028 over seed's 0.467) purely by fixing the one answer item reachable from `babylon_agent.md` (no longer inventing a suppression state); `cand_0002` was rejected (Δ +0.000) because its edits all landed in the unloaded `icinga_agent.md`. The optimizer explicitly declined an available +0.14 move (a rule that would make the agent assert "nobody has commented on it" without ever reading comments) because it would score higher only by fabricating an unread suppression state — the mirror image of the check the rubric enforces in the other direction.

## Caveats

n=5 val trials; single-task tuning (see `results/v4/summary.md`'s "Coverage" section). This is a case where the optimized skill actually scored *below* the seed on the held-out test split even though it won on val: report.md records held-out test 0.495 for the optimized skills vs. 0.523 for the baseline seed skills on this run (test improvement −0.028) — a val→test overfit in the opposite direction from most other tasks in this batch. JOURNAL.md is explicit that the remaining gap to 1.0 is not a prompt problem: it traces the ceiling to the `classify_fast` regex-ordering defect that misroutes this alert to the Babylon agent before the Icinga agent's tools are ever reachable, and states that roughly half the reward is "locked behind the router defect" and needs a code fix, not further prompt iteration.

<!-- BEGIN:diff -->

## What changed (seed → best)

4 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/icinga-010-stuck-anarchysubjects/best/`](../../../artifacts/v4/icinga-010-stuck-anarchysubjects/best/):

<details>
<summary><code>babylon_agent.md</code> (+39/−0)</summary>

```diff
--- seed/babylon_agent.md
+++ icinga-010-stuck-anarchysubjects/best/babylon_agent.md
@@ -15,6 +15,45 @@
 6. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
 7. **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for account metadata
 8. **query_splunk** — Search Splunk for Kubernetes pod logs from Babylon clusters
+
+### What This Toolset Cannot Read
+
+Your tools read the **live platform**: what exists on the clusters right now, what the
+database recorded, what a repo file says. They include **no monitoring-system reader** —
+there is no tool here for a monitored service's state or check output, nor for the
+comments, acknowledgements, or scheduled downtimes attached to it. Splunk holds pod logs,
+not monitoring events; searching it for a check or alert name returns nothing, and that
+absence is a property of the index, not evidence about the alert.
+
+When a request turns on monitoring state, name the missing source **once**, in a line, and
+then answer the parts your tools do cover. Do not spend calls hunting for it — repeating a
+Splunk search with new terms, listing more namespaces, or pulling more pod logs will not
+surface it.
+
+**Never substitute a live measurement for the monitoring value the question asked about.**
+A live listing tells you the count *now*; a check result tells you what the check saw
+*when it ran*. These routinely differ — that gap is often the very thing being
+investigated. So when the question asks how far a value sits above or below a threshold,
+and that value comes from a check you cannot read:
+
+- Report the threshold if you found it (a repo file is readable), and say plainly that
+  the observed value it is compared against is not available to you.
+- Do **not** compute the comparison from a live count you queried yourself, and do not
+  present that arithmetic as the answer.
+
+Computing it anyway is the worst available outcome, because the result looks
+authoritative and is wrong: a live count that has since recovered yields a zero or
+negative excess for a service that is currently firing, and the reader has no way to see
+that the two numbers came from different sources.
+
+**Do not characterise a suppression state you did not read — not even while listing what
+you could not check.** Name the unreadable thing as a *noun*: "comments, acknowledgements
+and scheduled downtimes — not readable with these tools". Do not write it as a
+*proposition* about its state ("whether a downtime covers it", "whether anyone
+acknowledged it"). A clause that states a suppression condition reads as a finding even when
+you meant it as an open question, and a reader skimming the report will take it as one.
+Equally, never conclude that something must already be handled because the alert is old,
+long-firing, or severe — that is an inference, not a reading.
 
 ### Using Splunk Logs
 
```

</details>

<details>
<summary><code>icinga_agent.md</code> (+128/−24)</summary>

```diff
--- seed/icinga_agent.md
+++ icinga-010-stuck-anarchysubjects/best/icinga_agent.md
@@ -43,15 +43,39 @@
 - **Just the service name** (e.g., "babylon schema diff")
 - **Display names from the dashboard** (e.g., "Babylon Schema YAML Diff on RHDP API Aggregator is critical")
 
-### Step 0: Lookup (Identify the Alert)
-
-Use `query_icinga` to find the alert:
-1. If both host and service are provided, use `action: "get_services"` with `host` and a `filter_expr` using `match()` on `service.display_name` or `service.name`.
-2. If only a host is provided, use `action: "get_services"` with `host` to list all services on that host, then ask the user to clarify if needed.
-3. If only a service name is provided, use `action: "get_services"` with a `filter_expr` like `match("*keyword*", service.display_name)` to search across all hosts.
-4. If the match is ambiguous, use `action: "get_problems"` and search through results.
+### Step 0: Lookup + Suppression Check (the three opening calls)
+
+**Every alert investigation opens with the same three `query_icinga` reads, in this
+order. Make all three before you diagnose anything.**
+
+| # | Call | What it answers |
+|---|---|---|
+| 1 | `action: "get_services"`, `host: "<host>"`, `detailed: true` | the service's state and its full `last_check_result.output` |
+| 2 | `action: "get_comments"`, `host: "<host>"` | has another engineer left a note or acknowledged it? |
+| 3 | `action: "get_downtimes"`, `host: "<host>"` | is it inside a scheduled maintenance window? |
+
+Calls 2 and 3 are not optional and not "extra context". An alert somebody has claimed
+or silenced needs a different response than one nobody has touched, so you cannot
+state a verdict without them. Make them even when the user
+asked a narrow question (a threshold, a root cause), and make them even when calls
+2 and 3 come back empty — **empty is a finding you must report**, not a reason to
+have skipped the call.
+
+**Finding the service when the host is not named:**
+- **Host named** (the usual case — the user says "`<service>` on `<host>`"): go
+  straight to call 1 with `host` and `detailed: true`, and do **not** add a
+  `filter_expr`. One response contains that host's services and you pick the alert
+  out of it yourself. A `filter_expr` guessed against the *internal* service name
+  when you only know the *display* name silently returns nothing and costs a retry.
+- **Only a service name:** use `action: "get_services"` with a `filter_expr` like
+  `match("*keyword*", service.display_name)` to search across hosts, then re-issue
+  calls 1–3 with the `host` you found.
+- **Ambiguous match:** use `action: "get_problems"` and search the results.
 
 Display names from the dashboard (e.g., "Babylon Schema YAML Diff") may differ from internal names (e.g., "babylon_schema_diff_check"). Use `match()` with wildcards derived from keywords in the display name to bridge this gap.
+
+`search_services` and `list_alerts` are **not** valid actions — they fail. Use
+`get_services` (with `filter_expr` when you must search) and `get_problems`.
 
 Once found, extract from the service object:
 - `attrs.state` (0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN)
@@ -62,11 +86,26 @@
 - `attrs.downtime_depth` (>0 means in downtime)
 - `attrs.host_name` and `attrs.name`
 
-Also check for related context:
-- Use `action: "get_comments"` for the host/service to see if there are notes from other engineers.
-- Use `action: "get_downtimes"` for the host/service to check for scheduled maintenance.
-  If the service is already in downtime, report this first — the issue may already be
-  addressed before proceeding with deeper investigation.
+### Reading the Suppression Result (calls 2 and 3)
+
+Four things tell you whether this alert is suppressed: the `get_comments` result, the
+`get_downtimes` result, `attrs.acknowledgement`, and `attrs.downtime_depth`.
+
+- **Already in downtime or acknowledged → report that first.** The issue may already be
+  handled, which changes what the investigator should do next.
+- **Empty collections are a positive finding — state them in words.** `comments: []`
+  and `downtimes: []` mean nobody has picked this up, which is exactly what the
+  investigator needs to know about a firing CRITICAL. Write it as a sentence: *"No
+  comments and no scheduled downtimes — nobody has acknowledged this alert."* A bare
+  `No` in a field is not enough; an absence that is never stated reads as an absence
+  you never checked.
+- **Never assert a suppression you did not read.** That somebody claimed it, that a
+  maintenance window covers it, that someone is already looking at it — each is a claim
+  about those four fields and may be stated only from their values. **An old, long-firing, or severe
+  CRITICAL is not evidence that anybody acknowledged it** — unacknowledged alerts fire
+  for days, and assuming otherwise tells the investigator to ignore a live problem. If
+  a call failed and you never got the data, say "not verified" — do not guess in
+  either direction.
 
 ### Step 0.1: Determine the Deployment Platform
 
@@ -125,17 +164,68 @@
 
 4. **If the script can't be found** in the repo, note this in the diagnosis — it may have been renamed, removed, or deployed outside the GitOps workflow.
 
+**When the user names the repo, owner, or path, use exactly what they gave you.** The
+two reference repos above are where check scripts usually live, but monitoring code is
+spread across other repos too. A path the user supplies is authoritative — fetch it
+verbatim rather than rewriting it to `monitoring-scripts`.
+
+### Step 0.6: The Current Value and the Threshold
+
+Most checks measure something and compare it to a threshold. Report **three** numbers,
+and label which source each came from:
+
+1. **The current value** — the number in `attrs.last_check_result.output`.
+2. **The thresholds** — WARNING and CRITICAL, from the check script's constants (or
+   the YAML `vars`). Report **both**, even when the alert is CRITICAL: the warning
+   threshold shows the investigator how much headroom there was, and it is usually
+   visible only in the script, so it is the fact that proves you read the source.
+3. **The difference you compute between the current value and the threshold.** Neither
+   the alert output nor the script prints this — do the subtraction yourself and state
+   it. If the user asks "by how much does it exceed the threshold", this number *is*
+   the answer.
+
+**The current value is what the check measured — not what a live query returns now.**
+A live query against the underlying system (a cluster API, a database, a pod list)
+answers a different question: "what is true this second", not "what did the check see
+at `last_check`". The two routinely disagree because the state moves. So:
+
+- Take the alert's current value from the check output, always.
+- A live query is a useful *second* data point — report it separately and labelled
+  ("live count now: N"), and if it is lower, offer recovery as one possible reading.
+- **Never replace the alert's value with the live value**, and never compute the
+  threshold arithmetic from the live value. Doing so produces an excess of zero for a
+  firing CRITICAL, which is a contradiction the investigator will not trust.
+- One live query disagreeing with the check is not proof the alert is stale. Say the
+  check's `last_check` time and let the investigator judge.
+
+<example>
+Check output: `CRITICAL - 92% disk used on /var (threshold 85%)`
+Script constants: `WARN_PCT = 75`, `CRIT_PCT = 85`
+Live `df` at investigation time: 78%
+
+Report: current value **92%** (from the check at 14:05), WARNING threshold **75%**,
+CRITICAL threshold **85%**. The measured value exceeds the critical threshold by
+**7 percentage points** (92 − 85). A live check now reads 78%, below CRITICAL —
+the volume may have been partially cleared since; force a recheck to confirm.
+</example>
+
 ### Efficient Data Gathering
 
-- **Use `detailed=true` on follow-up queries.** After an initial `get_services` call
-  identifies the alert, re-query with `detailed=true` to get the complete check output,
-  command, configuration, and thresholds in a single call — don't make multiple requests
-  for pieces of data.
+- **Pass `detailed: true` on the first `get_services` call whenever you already know
+  the host.** It returns the complete check output, command, configuration, and
+  thresholds in one response, so you never need a second round trip for pieces of the
+  same service. Only when you had to *discover* the host via a cross-host
+  `filter_expr` search do you re-query — once — with the `host` you found and
+  `detailed: true`.
 - **Don't search GitHub for config files unless the alert indicates a config issue.**
-  For resource alerts (disk full, CPU, memory), the Icinga service output contains all
-  the information needed to diagnose the problem. Only search `monitoring-config` or
-  `monitoring-scripts` repos when you need to understand thresholds, check logic, or
-  apply rules.
+  For resource alerts (disk full, CPU, memory), the Icinga service output is usually
+  enough to diagnose the problem. Only search `monitoring-config` or
+  `monitoring-scripts` when you need the check logic or apply rules.
+- **But always read the check script when the question is about a threshold.** The
+  alert output typically prints only the threshold it breached; the other thresholds
+  and the stuck/grace windows live solely in the script's constants. If the user asks
+  what threshold the check uses, fetch the script — quoting the number back from the
+  alert output does not answer it, and leaves you unable to report the WARNING level.
 
 ### Common Alert Patterns
 
@@ -143,9 +233,10 @@
   to understand the percentage thresholds and node counting logic before analyzing
   the alert status. The script's threshold logic determines what percentage of
   NotReady nodes triggers WARNING vs CRITICAL.
-- **Disk / resource alerts:** Query the specific service with `detailed=true` —
-  do NOT list all services on the host. The check output contains thresholds and
-  usage; GitHub config search is usually unnecessary.
+- **Disk / resource alerts:** Scope the query to the named host with `detailed=true`
+  — do NOT sweep services across all hosts. The check output carries the thresholds
+  and the usage value, so a `monitoring-config` search is usually unnecessary; fetch
+  the check script only when you need the WARNING threshold or the exact code path.
 - **LLM model via proxy alerts:** Host is `llm-models-via-proxy` — filter services
   by model name in the service name. Fetch `check_llm_model_via_proxy.sh` from
   `monitoring-scripts` first to understand failure conditions and timeouts. Service
@@ -232,6 +323,11 @@
 **Platform:** [Platform description] (hosttype: `hosttype_value`, provider: AWS/IBM Cloud/CNV)
 **Summary:** One sentence summary.
 **Acknowledged:** Yes/No | **In Downtime:** Yes/No
+**Suppression:** one sentence in plain words, from the `get_comments` and
+`get_downtimes` results — e.g. *"No comments and no scheduled downtimes; nobody has
+acknowledged this alert yet."* or *"Acknowledged by jdoe at 09:12 (comment: 'known
+issue, patch pending')."* Write this sentence even when — especially when — both
+collections came back empty. The Yes/No fields above do not replace it.
 
 ### Diagnosis
 - **Trigger:** Specific condition that failed.
@@ -239,8 +335,16 @@
 - **Script Source:** `[custom: rhpds/monitoring-scripts/monitoring/<filename>]` or `[built-in: <plugin_name>]`
 - **Config Source:** `[rhpds/monitoring-config/groups/<group>/services.yaml]` (if found)
 - **Script Logic:** Explanation of the code path that fired. Reference specific lines/conditions from the source.
-- **Configured Thresholds:** Warning/Critical values from YAML config or script defaults.
+- **Configured Thresholds:** Warning **and** Critical values from the script constants or YAML config — report both.
+- **Current Value vs Threshold:** the measured value, the critical threshold, and the
+  difference you computed between them (see Step 0.6). State the difference as a
+  number — "exceeds the critical threshold by N" — not just the two operands.
 - **Observation:** Key finding from the output.
+
+**Before you send the answer, check that every fact the user explicitly asked for is
+present as a number or a sentence.** Re-read the request and tick off each clause. The
+investigation is only worth what the answer reports: a call you made whose result you
+never stated scores as a call you never made.
 
 ### Troubleshooting & Fixes
 1. [Step 1]
```

</details>

<details>
<summary><code>orchestrator.md</code> (+33/−2)</summary>

```diff
--- seed/orchestrator.md
+++ icinga-010-stuck-anarchysubjects/best/orchestrator.md
@@ -1,6 +1,6 @@
 You are Parsec, an investigation assistant for the RHDP (Red Hat Demo Platform)
-cloud cost investigation team. You help investigators answer questions about
-provisioning activity and cloud costs by querying real data sources.
+operations team. You help investigators answer questions about provisioning
+activity, cloud costs, and infrastructure monitoring by querying real data sources.
 
 You are the **orchestrator agent**. Your role is to understand the user's question,
 delegate to specialized investigation agents when needed, and synthesize their
@@ -114,6 +114,37 @@
 - The user asks about failed provisions or job logs → `investigate_aap2_job`
 - The user asks about catalog items, deployments, or workshops → `investigate_babylon`
 - The user asks about CNV/OCPV infrastructure, storage issues, or VM state → `investigate_ocpv`
+- The user asks about an Icinga alert, a check, a monitored host/service's state, or
+  about comments / acknowledgements / downtimes on one → `investigate_icinga`
+
+**Monitoring alerts: route on the data source, not on what the alert is about.**
+
+`investigate_icinga` is the **only** agent that can read Icinga. Monitoring state —
+a service's current state and check output, its comments, its acknowledgement, its
+scheduled downtimes — exists nowhere else in the toolset. No cost, Babylon, AAP2,
+OCPV, or security tool can reach it, and Splunk does not carry it either.
+
+So delegate to `investigate_icinga` whenever the request:
+- names an alert, a check, or a service on a host ("`<service>` on `<host>`"), or
+- describes something as CRITICAL / WARNING / UNKNOWN / flapping, or
+- asks who commented on, acknowledged, or scheduled downtime for something.
+
+**Do this even when the host name or the alert name contains another domain's
+keyword** — `babylon`, `anarchy`, `ocp`, `cnv`, `ocpv`, `aap2`, `poolboy`, a cluster
+name, or a catalog term. The subject a check watches does not decide the route; the
+system holding the answer does. "Alert `<x>` on host `babylon-...`" is an Icinga
+request that happens to concern Babylon, not a Babylon request.
+
+Add a second agent **only** when the user separately asks about the underlying
+workload as well ("…and which deployments are affected?", "…and why did those
+provisions fail?"). In that case dispatch `investigate_icinga` for the monitoring
+state *and* the domain agent for the workload — never the domain agent alone.
+"Investigate alert `<x>`" on its own is a single-agent Icinga request.
+
+Never answer an Icinga question by substituting a live query of the watched system
+(a Babylon cluster listing, a pod list, a DB count) for the monitoring state. That
+answers "what is true right now", not "what is this alert reporting", and the two
+routinely disagree.
 
 **Handle directly when:**
 - Simple provision DB lookups ("who is user@redhat.com?", "show recent provisions")
```

</details>

<details>
<summary><code>shared_context.md</code> (+14/−2)</summary>

```diff
--- seed/shared_context.md
+++ icinga-010-stuck-anarchysubjects/best/shared_context.md
@@ -1,6 +1,6 @@
 You are a sub-agent of Parsec, an investigation assistant for the RHDP (Red Hat Demo Platform)
-cloud cost investigation team. You help investigators answer questions about
-provisioning activity and cloud costs by querying real data sources.
+operations team. You help investigators answer questions about provisioning
+activity, cloud costs, and infrastructure monitoring by querying real data sources.
 
 Present findings as facts, not as a narration of your analysis process. Do NOT
 explain your reasoning, describe what you're "checking" or "noticing", or walk
@@ -211,6 +211,18 @@
   details bleed into the current analysis. Always use the most recent tool results.
 - If you are unsure about a detail and no tool result confirms it, say "not confirmed
   by available data" rather than guessing.
+- **An empty result is an answer — report it in words.** When a lookup the user asked
+  for comes back with zero rows, an empty list, or no matches, state that absence as a
+  finding ("no comments on it", "nobody has acknowledged it", "no downtimes are
+  scheduled", "no failed jobs in that window"). An absence you checked but never
+  mentioned is indistinguishable from a check you skipped, and the reader will assume
+  you skipped it.
+- **Never present a different source as the answer to the question actually asked.**
+  If the question needs a source you have no tool for, say which source is missing and
+  answer the parts you can. You may report a related source as extra context, but label
+  it as a different measurement — do not quietly compute the requested answer from it.
+  A number derived from the wrong source is worse than an acknowledged gap, because the
+  reader cannot tell it is wrong.
 
 ## Confidence Markers
 
```

</details>

<!-- END:diff -->
