# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I diagnosed (the trajectories/ files are score-only — the real traces are elsewhere)

`trajectories/*.json` in this dir carry no `trace` and an empty `tool_calls` list. The
actual transcripts are reachable via `rollout.metadata.trial_dir`:

- `<trial_dir>/*/*/agent/agent.jsonl` — full tool-call transcript + final answer
- `<trial_dir>/*/*/verifier/reward-detail.json` — **per-item** miss list (which required
  string / count / forbidden phrase fired). This is the highest-value file in the run.

I also read the task's own authored spec, which states the intended mechanism outright:
`.../bench-v6-harbor-tasks/bench-v6-platform-158-.../{instruction.md,provenance.md,tests/expected.json}`
plus `seeds/platform.json` (the job log body the agent is supposed to read).

Scores across the 10 seed trials: **2 × 1.0 (t6, t8), 8 × 0.275–0.362.** Not noise — a
clean bimodal split with a single discriminator.

## The discriminator (one binary branch decides the whole task)

The task hands the agent a lab GUID **and** a provisioning job id + controller, then asks
for the account, the region, and the instance inventory. The region exists in exactly one
place: a line in that job's log. `describe_instances` is region-scoped and defaults to
`us-east-1`, where the account has nothing — returning `{"instance_count": 0}` as a
*successful empty result*, not an error. The task's `kind` is literally `"trap"`.

| | called `query_aap2 get_job_log`? | outcome |
|---|---|---|
| t6, t8 | **yes** | got region → 3 instances → **1.0** |
| t0–t5, t7, t9 | **no — never called it at all** | swept 4–13 guessed regions, all empty → 0.275–0.362 |

The 8 failing trials went straight to cloud inspection, got `us-east-1` → 0, then guessed
`us-west-2`, `eu-west-1`, `ap-southeast-1`, `ca-central-1`, … and concluded "no EC2
instances / not launched yet / torn down". t9 tripped the `torn-down` forbidden phrase.
Every failing trial missed `region`, `bastion-id`, `bastion-stopped`, `node-type` and the
instance count — i.e. **four of five required items plus the count all hang off that one
skipped call.**

Attribution of the wrong branch: the `describe_instances`/CloudTrail calls belong to the
security agent, whose tool list has **no `query_aap2`**. So the wrong choice is made
*upstream*, in `orchestrator.md`, which delegated to `investigate_security` instead of
`investigate_aap2_job`. Seed-0's orchestrator even offered "Investigate AAP2 job …" as a
*follow-up button* after declaring the lab not built — it knew about the job and deferred it.

Root cause, stated generally: **`orchestrator.md` only reaches `investigate_aap2_job` for
failure triage** ("failed provisions, job logs, AAP2 errors, root cause of why a job
failed"). Here the job *succeeded*, so nothing routed there — and nothing anywhere told
the orchestrator that an instance inventory even needs a region, or that the account pool
doesn't carry one.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Successful provisioning job never read, so a deployment parameter it alone carries is never obtained | platform-158 (8/10 trials) | `orchestrator.md` routes to AAP2 only on *failure*; no rule says a successful job log is a source of deployment facts | KNOWLEDGE (routing) | routing rule + new AAP2 section |
| 2 | Region-scoped cloud lookup left at its default, empty result read as absence | platform-158 (8/10) | nothing states `describe_instances` defaults to `us-east-1` and returns empty-success; no rule forbids guess-sweeping regions | KNOWLEDGE + BEHAVIORAL | domain rule + orchestrator fact |
| 3 | Scoped emptiness upgraded to a verdict ("torn down") | platform-158 (t9 hit `torn-down`; others implied it) | no general rule separating "not in this scope" from "does not exist" | BEHAVIORAL | shared_context rule |
| 4 | Unavailable tool retried with reworded args | platform-158 (all 10 trials) | `query_provisions_db` returns an explicit "not modelled" error; agents re-called it with new column guesses 2–3× | BEHAVIORAL | shared_context rule |

Cluster 4 costs no reward directly (tool_calls is ordered-subsequence, so extra calls
don't subtract) but burns the call budget that the skipped AAP2 hop needed.

## Changes made this iteration (one row per edit)

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | routing | `orchestrator.md` | Agent #2 blurb extended to successful jobs; new "Provisioning jobs are a source of deployment facts, not just failure reports" block. Trigger is **conditional**: job named AND the answer needs a deployment parameter the question didn't supply; explicit opt-out when the parameter is already known. | yes — opt-out keeps region-supplied and non-scoped questions on their current path |
| 2 | knowledge | `orchestrator.md` | New "EC2 instance inventories are region-scoped" block at the decision point: states the `us-east-1` default + empty-success, states that the account pool and provisions DB **do not** record a region, and says resolve-region-then-delegate. Also rebuts an unconfirmed-region empty inventory coming back from a sub-agent. | yes — only fires when region is absent from the question |
| 2 | knowledge/behavioral | `security_agent.md` | New "Region is a required input, never a default" section: ranked region sources (passed-in → CloudTrail → record field → *escalate for the job log*), ban on guess-sweeping, worked example with placeholders. | CloudTrail **retained** as the no-job fallback (seed's only mechanism) and promoted to source 2 |
| 1 | knowledge | `aap2_agent.md` | New "Reading a SUCCESSFUL job for deployment parameters" section: read the log *body* (playbooks print inputs as early task output), pass literals through verbatim, config-chain trace not required for a parameter question, surface the region explicitly for the downstream cloud lookup. | yes — scoped to parameter questions; failure workflow untouched |
| 3 | behavioral | `shared_context.md` | New "Scoped Lookups: Empty Is Not Absent" — generalized past region to cluster/namespace/time-window/partition. Explicit positive-evidence carve-out so a genuinely retired resource can still be reported. | carve-out + reconciled with the seed's "empty results are themselves the answer" line |
| 1 | behavioral | `shared_context.md` | New "Use Every Identifier the User Gave You" — hedged ("a question you can already answer is finished") so it doesn't force calls on incidental identifiers. | hedge is load-bearing |
| 4 | behavioral | `shared_context.md` | New "Unavailable Tools: Pivot, Don't Retry". | matches seed's existing no-retry guidance |

## Verify-the-fix

The decision point is the orchestrator's first routing choice on a question that names a
provisioning job and asks "in which region / how many instances".

- **Cluster 1/2 (the 8 failing trials):** both conditions of the new orchestrator rule match
  literally — the question names "AAP2 job … on controller east", and asks "in which
  region", the parameter the rule names explicitly. The region block then removes the
  specific wrong inference the traces show ("I have the account id, that's enough to ask
  for instances") by stating that the account pool carries no region. Checked against the
  text the orchestrator actually reads: the seed line "Use the AWS account numbers directly
  to query instance details" sat directly on the failing path, so I amended **that line
  in place** rather than only appending a block elsewhere.
- **Second-line defence:** if routing still goes to security first, the region section stops
  the 13-region sweep and makes the agent hand back "region unconfirmed; the job log records
  it", which the new orchestrator paragraph tells it to act on by re-delegating. Costs extra
  calls but converges instead of emitting a wrong answer.
- **Cluster 3 (t9's `torn-down` hit):** the forbidden phrase came from an unconfirmed-region
  empty result. Both the shared_context rule and the security section now forbid exactly
  that inference while explicitly permitting the claim when a record positively shows it.
- **Honest limit:** cluster 1/2 rests mainly on the orchestrator rule firing. I verified the
  trigger wording against the literal question text, but prose routing is probabilistic —
  this should move 8 trials toward the t6/t8 path, not guarantee all 8.

## Process & features used

- **Subagents:** two read-only audit subagents, both of which changed the edit materially:
  1. **Overfitting audit** → caught that I had deleted CloudTrail as the no-job region
     fallback (regression risk for tasks with no AAP2 job), that "the log is the **only**
     region source" contradicted my own ranked list, that the termination-language ban had
     no positive-evidence carve-out, and that two triggers were blanket. All fixed.
  2. **Verify-the-fix audit** → the important one. Found (a) the orchestrator never learns
     that instance lookups are region-scoped, so the fix had no text at the actual decision
     point, and (b) I had instructed `security_agent.md` to call `query_aap2`, **a tool that
     agent does not have**. Both fixed: added the region block to `orchestrator.md`, and
     rewrote the security agent's source list to escalate instead of calling.
- **Serial editing** rather than per-issue worktrees: all four issues are one causal chain in
  four files with no overlapping hunks, so parallel edit-agents would have added merge risk
  for no coverage gain. Fan-out went into *diagnosis and adversarial review* instead.
- **Prior iterations:** none — iteration 1, `RUNMAP.md`/`LEDGER.md` empty, `rejected.jsonl`
  absent. Nothing to build on or avoid.

## Good things to PRESERVE (do not let a future iteration undo these)

- **`reward-detail.json` is how you diagnose this suite.** Per-item `required_missed` /
  `counts_missed` / `forbidden_hit` tells you exactly which sentence was missing. Don't
  diagnose from the reward scalar in `trajectories/`.
- **CloudTrail as the region fallback when no provisioning job is named.** I nearly deleted
  it; it is the only region-discovery route for tasks that don't hand you a job.
- **The positive-evidence carve-outs** on the absence-language rules. Without them a
  genuinely retired environment can never be reported as retired.
- **Before adding a rule telling an agent to call tool X, check X is in that agent's tool
  list.** The security agent has no `query_aap2`; a rule that assumes otherwise is dead text.

## Deliberately skipped (cluster + why)

- `account-id` miss in t2/t4/t5: a downstream symptom of the same skipped chain (those
  trials never resolved the account either), not an independent cluster.
- Response-formatting / citation rules: no trial lost points on format; `completion` was
  1.0 everywhere.
- No escalation needed — every tool the golden chain requires exists and is reachable from
  the routed agents. This failure is genuinely prose-fixable, with one caveat worth
  recording: the region fix must live in `orchestrator.md`, because the agent that owns
  `describe_instances` cannot reach the job log that holds the region.
