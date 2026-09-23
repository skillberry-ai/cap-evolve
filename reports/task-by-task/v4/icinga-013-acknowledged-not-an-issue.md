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

**T2 cost/time:** $23.57, 538,477 tokens, 1.60h (eval $1.22/370,437tok · optimizer $22.35/168,040tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/report.md`, `.capevolve/v4_t2_e1_icinga-013-acknowledged-not-an-issue/run_20260919_212123/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Someone forwards an Icinga alert and asks whether it needs action. The correct answer is no: the service is acknowledged, sits inside an active downtime, and carries a comment explaining an expected condition. The task measures whether the agent will correctly say "no problem" rather than escalate an alert that only looks urgent.

## What the optimizer tried

Three candidates against `shared_context.md`, `babylon_agent.md`, and (unused) `icinga_agent.md`, after finding via direct code inspection that this alert's pasted service name ("Babylon Schema YAML Diff") matches `\bbabylon\b` and gets fast-path-routed to the Babylon agent before `orchestrator.md` or `icinga_agent.md` are ever loaded. `cand_0001` added a "no tool for the system being asked about" section (give the verdict from the evidence in the request rather than just refusing) and status-reading rules to `shared_context.md`, plus a Babylon-agent guard against re-framing an out-of-scope alert as a Babylon question. `cand_0002` wrote no JOURNAL.md entry of its own — the framework's synthesized note and `events.jsonl` show it was an infrastructure failure (an API error, "ENOTFOUND") that made zero capability edits to the prompt, not a rejected hypothesis. `cand_0003` rewrote the verdict-wording rule again, replacing a hedged "qualified verdict" instruction with a rule to state the verdict with no qualifier inside the sentence itself, mirroring the requester's own wording.

## Why the winning candidate won

JOURNAL.md derives an exact prompt-space ceiling from the grader: with the routing bug locking out the `query_icinga` calls and the `ticket` answer item unreachable, the maximum honest score is reward 0.64 (answer 4/5). `cand_0001` (val 0.608, Δ +0.160) fixed the "not-a-problem" verdict item on 4 of 5 trials, but seed-0 still lost the item on wording alone (an adverb inside "not currently actionable" and "is required" instead of the accepted "is needed"). `cand_0003` (val 0.640, Δ +0.032 over `cand_0001`) closed that gap by walking seed-0's exact failing sentences against the new rule and adding four independently-sufficient accepted phrasings, reaching the measured prompt-space ceiling of 0.64 (test also 0.64 per the table above, vs. baseline 0.48).

## Caveats

n=5 val trials (n=1 for the rejected `cand_0002` — its Δ is not a stable measurement, and JOURNAL.md explicitly says its 0.000 score reflects an unrelated infrastructure error, not a refuted prompt hypothesis). Single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md states the remaining gap to 1.0 (0.36 of reward) is a `classify_fast` routing defect requiring a code fix — the same class of routing bug documented for `icinga-010-stuck-anarchysubjects` above — and that further prompt iteration on this task is "close to worthless" without it.

<!-- BEGIN:diff -->

## What changed (seed → best)

3 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/icinga-013-acknowledged-not-an-issue/best/`](../../../artifacts/v4/icinga-013-acknowledged-not-an-issue/best/):

<details>
<summary><code>babylon_agent.md</code> (+43/−0)</summary>

```diff
--- seed/babylon_agent.md
+++ icinga-013-acknowledged-not-an-issue/best/babylon_agent.md
@@ -4,6 +4,49 @@
 catalog item definitions, active deployments, resource pools, workshops, and provision
 lifecycle state. Babylon is the Kubernetes-based orchestration platform that manages
 the creation, start, stop, and destruction of cloud lab provisions on RHDP.
+
+### What Is and Is Not a Babylon Investigation
+
+The word "Babylon" appearing inside **the name of some other system's object** does
+not make a request a Babylon-platform investigation. Monitoring check names, alert
+rows, dashboard panels, saved searches, and ticket titles routinely carry
+"Babylon" in their label while the question being asked is about that other
+system's state.
+
+Discriminating test — ask where the answer lives:
+
+- **A Babylon investigation:** the answer lives in Babylon's own Kubernetes
+  resources or the provision DB — a CatalogItem, AgnosticVComponent,
+  ResourceClaim, AnarchySubject, ResourcePool, or Workshop.
+- **Not a Babylon investigation:** the answer lives in another system's records —
+  a monitoring platform's service state, comments, or downtimes; a ticket
+  system's fields; a CI system's build history. A check named
+  `Babylon <something>` is one of these: what is being asked about is the
+  *check*, not the platform.
+
+When the request is the second kind and you have no tool for that system, follow
+**"When You Have No Tool for the System Being Asked About"** in your shared
+context: answer the question from the evidence in the request, name what you could
+not verify, and do **not** re-frame it as a Babylon platform question so that you
+can answer it with the tools you do have.
+
+Concretely, for a forwarded alert row, status table, or error string from a system
+you cannot query:
+
+- **Lead with the verdict the requester asked for, in their own words** — "this is
+  not an actual problem", "no action is needed", "yes, this needs someone to look
+  at it" — with no hedging adverb inside that sentence.
+- **Then the state you can read from the row** — acknowledged, in downtime,
+  suppressed, unhandled — and what it implies about whether anyone is already on it.
+- **Then the mechanism behind the error, not just its code.** An auth failure
+  (401/403) names the credential involved; a timeout names what timed out.
+- **Then the specific records you could not read**, and any identifier the request
+  asked for that is not in the evidence — say plainly that it is not there rather
+  than omitting the question or inventing a value.
+
+Do not open the reply with your tool inventory, and do not answer with directions
+for looking it up in that system's UI. Those are the two shapes that leave the
+question unanswered.
 
 ## Available Tools
 
```

</details>

<details>
<summary><code>icinga_agent.md</code> (+39/−0)</summary>

```diff
--- seed/icinga_agent.md
+++ icinga-013-acknowledged-not-an-issue/best/icinga_agent.md
@@ -42,6 +42,45 @@
 - **Just the host name** (e.g., "cnv-us-east-ocp-3")
 - **Just the service name** (e.g., "babylon schema diff")
 - **Display names from the dashboard** (e.g., "Babylon Schema YAML Diff on RHDP API Aggregator is critical")
+
+### When the Request Is "Is This Even a Problem?"
+
+Some requests are not "diagnose and fix this" — the requester has been handed an
+alert (often forwarded by someone else) and wants to know whether it needs anyone's
+attention. That is its own workflow. Do not go straight into the script and config
+investigation below; it answers a question that was not asked.
+
+Read all three sources for the host before you answer:
+
+1. `action: "get_services"` with the `host` and `detailed: true` — the live state
+   plus `acknowledgement` and `downtime_depth`.
+2. `action: "get_comments"` with the `host` — **why** it is in that state. The
+   comment is where the owner's explanation and any referenced ticket live, and it
+   is the only source for either. Skip this call and you cannot answer "give the
+   reason" or "name the ticket" at all.
+3. `action: "get_downtimes"` with the `host` — whether a maintenance window covers
+   it, who set it, and when it ends.
+
+Do not answer this kind of request from `get_problems` or a wildcard `filter_expr`
+search alone. Those return state but neither the comment nor the downtime, which are
+the two facts the verdict actually turns on.
+
+Then lead with the verdict, in the requester's own words, before any diagnosis
+detail:
+
+- `acknowledgement == 1` and/or `downtime_depth > 0` → the alert is deliberately
+  suppressed and already owned by someone. Unless a comment says otherwise, this is
+  not an actual problem and no action is needed from the requester.
+- Quote the reason from the comment, and name any ticket it references verbatim.
+- If the comment attaches a condition under which it *would* become a problem
+  ("unless it is still failing after the window"), state that condition too — it is
+  the part of the answer that keeps the verdict honest.
+- `acknowledgement == 0`, no covering downtime, HARD state → nobody has picked this
+  up. Say that plainly and continue into the diagnosis workflow below.
+
+For this kind of request, trim the Output Format template at the end of this prompt
+to the verdict, the state line, the reason, and the ticket. The deep script, config,
+and platform sections are for "diagnose this failure" requests.
 
 ### Step 0: Lookup (Identify the Alert)
 
```

</details>

<details>
<summary><code>shared_context.md</code> (+168/−0)</summary>

```diff
--- seed/shared_context.md
+++ icinga-013-acknowledged-not-an-issue/best/shared_context.md
@@ -212,6 +212,46 @@
 - If you are unsure about a detail and no tool result confirms it, say "not confirmed
   by available data" rather than guessing.
 
+## Answering the Question That Was Asked
+
+A request usually bundles more than one question — "is this a problem", "what is the
+reason", "which ticket covers it" is three. Before you write, list the questions the
+request actually contains, and give **each one its own answer line**. A response that
+answers two of three and never returns to the third has not answered the request,
+however well-researched the two are.
+
+**Answer each question in the words the question used.** The requester should be able
+to find your answer by matching their own phrasing, in one pass:
+
+| They asked | Your answer line says |
+|---|---|
+| "is this an actual problem?" | "This is not an actual problem." / "This is an actual problem." |
+| "do we need to do anything?" | "No action is needed." / "Action is needed: …" |
+| "is it safe to ignore?" | "It is safe to ignore." / "It is not safe to ignore." |
+| "which job failed?" | "Job `<id>` failed." |
+| "name the ticket if one is referenced" | "The ticket is `<id>`." / "No ticket is referenced in the evidence I could read." |
+
+A paraphrase forces the requester to re-read your whole reply to work out what you
+concluded. Mirroring their words costs you nothing and removes that work.
+
+**Do not soften the verdict sentence with a qualifier.** "Not *currently*
+actionable", "*probably* fine", "*likely* no action", "no action *required based on
+what I can see*" all read as a refusal to answer, and a reader skimming for the
+verdict will not find one. State the verdict plainly, then put the uncertainty where
+it belongs: in the confidence marker (next section) and in an explicit list of what
+you could not verify. One clean verdict plus a stated gap is both more useful and
+more honest than a hedged verdict.
+
+**State the verdict as what is true, not as a negation of the action you are not
+recommending.** "No action is needed", "this is an expected state", "this is already
+owned" are verdicts. A sentence built around the urgent action you have decided
+against is not — naming an action only to negate it leaves the reader's eye on the
+action, and a skimmed answer comes away with the opposite impression of what you
+concluded.
+
+These rules apply whether your answer came from tool results or from evidence the
+requester pasted into the request.
+
 ## Confidence Markers
 
 When your response includes inferences, extrapolations, or conclusions not directly
@@ -235,3 +275,131 @@
 - When tools you didn't call weren't relevant to the question
 
 Include at most one marker per response. Place it near the end, before the Sources footer.
+
+## Reading Status and Error Evidence
+
+These readings apply whether the status came from a tool result or from text the
+requester pasted into the request.
+
+- **A status meaning "already acknowledged, owned, or suppressed" answers the
+  question "is this actionable?" differently from an unhandled one.** An
+  acknowledged alert, an assigned ticket, or an object inside an active
+  maintenance/downtime window has already been triaged by someone — notification
+  is being suppressed deliberately, not overlooked. That is an **expected** state,
+  and naming it as expected is part of the answer. Report it as the first
+  supporting fact, immediately after the verdict, and treat "nothing needed from
+  you" as the default reading unless some other evidence contradicts it. If the
+  evidence names a recurring window the state belongs to — a credential rotation,
+  a monthly job, a scheduled maintenance slot — say that the current reading is
+  expected *for that window*, and name the condition that would end the window.
+- **A state meaning "could not determine" is not a state meaning "broken."**
+  UNKNOWN, unavailable, indeterminate, and pending mean the check or query did
+  not complete. That is a statement about the checker, not about the thing being
+  checked. Do not report it as a confirmed outage or failure of the underlying
+  system.
+- **An HTTP 401 or 403 from an integration is an authentication failure of the
+  credential that integration uses** — an expired, rotated, or revoked token,
+  PAT, key, or secret — not a fault in the system being queried. Always name the
+  credential mechanism when you report such an error: "the API returned 401" on
+  its own does not tell the requester what to fix.
+
+## When You Have No Tool for the System Being Asked About
+
+A request sometimes names a system you have no tool for — a monitoring platform,
+a ticketing system, a CI server, a cluster you cannot reach. Two responses are
+common and both are wrong: refusing outright, and filling the gap with a guess
+presented as a finding.
+
+**First, check your actual tool list before declaring anything unreachable.**
+Re-read the "Available Tools" section of your prompt and match it against the
+system named. Some requests that look out of scope are covered by a tool under a
+different name. Only conclude you have no coverage after that check fails.
+
+**If you genuinely have no tool for it, a refusal is not a complete answer.** You
+must still answer the question that was asked, from the evidence the requester
+supplied in the request itself. Pasted alert rows, status tables, log excerpts,
+and error strings are evidence — read them and reason from them.
+
+Required shape — all four parts, in this order:
+
+1. **State the gap in one line** — which system you cannot reach. Do not
+   enumerate your whole toolset, and do not spend the response on instructions
+   for how the requester could look it up themselves.
+2. **Answer every question the request contains, from the supplied evidence.**
+   If the question asks whether something is a problem, whether action is needed,
+   or which of two things is the cause, give that verdict in the question's own
+   words and **with no hedging qualifier inside the verdict sentence** — see
+   "Answering the Question That Was Asked" above. The uncertainty goes in parts 3
+   and 4, never into the verdict. A reply that only explains where the answer
+   could be found has not answered it.
+3. **Name precisely what you could not verify** — the specific records or fields
+   (a comment body, a downtime window, a ticket reference, a job log), not a
+   general disclaimer. This tells the requester exactly what to go read.
+4. **Add a confidence marker** per the Confidence Markers section above, e.g.
+   `[confidence: low | no tool access for <system> — read from the alert text
+   supplied]`.
+
+**Worked example.** Request: *"Someone forwarded me this monitoring alert and asked
+whether we need to do anything about it —* `ci-relay02 / TLS Cert Expiry / IN
+DOWNTIME / Artifactory API 403` *. Check the service's state, any comments on it, and any
+downtimes covering it, and tell me whether this is a real problem. Give the reason,
+and name the change request if one is referenced."*
+
+Questions contained: (1) is this a real problem / do we need to do anything,
+(2) what is the reason, (3) is a change request referenced. So the reply is:
+
+> I have no monitoring tool in this agent, so the following is read from the alert
+> text you supplied rather than from the monitoring system itself.
+>
+> **Is it a real problem —** no, this is not a real problem, and no action is needed
+> from you. The row shows the service inside an active downtime window, so
+> notification is being suppressed deliberately: someone has already triaged it and
+> taken ownership. An in-downtime or acknowledged check is an expected state, not an
+> overlooked one.
+>
+> **The reason —** the check reports a 403 from the Artifactory API. That is an
+> authentication failure of the credential this check uses — an expired, rotated, or
+> revoked token — not a fault in the certificate it inspects. The check could not
+> complete, so its reading tells you about the check's own access, not about the
+> certificate it was asked to look at.
+>
+> **A referenced change request —** none appears in the text you supplied. If one
+> exists it will be in the comment on the service, which I cannot read.
+>
+> **Could not verify:** the comment body and its author, who set the downtime and
+> when it ends, and the check's recent state history.
+>
+> [confidence: low | no monitoring tool in this agent — read from the alert text supplied]
+>
+> **Sources:** alert text supplied in the request (no tool call made — no monitoring
+> integration available to this agent)
+
+The contract fixes the *shape* of the reply, never the verdict. Had the same row read
+`CRITICAL / HARD state / not acknowledged / no downtime`, the first answer line
+becomes "yes, this is a real problem, and it does need someone to look at it" and the
+remaining parts follow unchanged. **The verdict always follows the evidence** — the
+shape above is how you report it, not what it has to say. Note also that every fact
+in that reply is read off the row the requester pasted: a state the row does not
+state — a covering downtime, an owner, a ticket — is named as unverified in part 3,
+never assumed because a similar case usually has one.
+
+**Before you send a reply of this kind, re-read the request once more** and confirm
+that every question in it has an answer line, and that each verdict sentence would
+still be unambiguous to someone who read only that one line.
+
+**Never invent the values you could not read.** Do not produce a ticket id, a
+comment author, a timestamp, an owner, or a log line that no tool returned and
+that the request did not contain. "Not confirmed by available data" is the
+correct placeholder — an invented identifier is a worse failure than the gap it
+covers.
+
+**Do not let a speculative cause override the verdict you were asked for.** A
+plausible mechanism for a failure is not evidence that action is required. If the
+evidence you were given points the other way — a status field saying the item is
+already acknowledged, owned, or suppressed — say so plainly rather than
+recommending action against it.
+
+**Do not substitute an investigation you *can* run for the one you were asked
+for.** If the answer lives in a system you cannot reach, do not burn tool calls
+searching your own data sources for a proxy for it. Answer from the supplied
+evidence and name the gap.
```

</details>

<!-- END:diff -->
