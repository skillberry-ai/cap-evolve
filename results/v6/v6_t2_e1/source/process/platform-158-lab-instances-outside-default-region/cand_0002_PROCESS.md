# PROCESS — cand_0002 (explainability; REQUIRED)

## Headline

The one remaining failing trial does not fail for the reason cand_0001 targeted.
It fails because **cand_0001's own rule told the agent not to retry a call that
had merely timed out.** This iteration splits that rule in two: a *refusal*
(the service answered, and the answer is "never") still means pivot; a
*no-answer* (the service never answered) means re-issue once.

## 1. Diagnosis

Champion cand_0001 scores 4/5 trials at 1.0 and one (seed-3) at **0.375**
(completion=1.0, tool_calls=0.667, answer=0.25). Not a noisy spread — one trial
with one discrete divergence.

The 4 passing trials all run the identical chain:

```
query_provisions_db          -> "is not modelled by the simulation"  (a refusal; pivot is correct)
query_aap2 get_job_log       -> job log, which carries the region
query_aws_account_db {name}  -> account id
query_aws_account describe_instances {account_id, region} -> 3 instances
```

seed-3 diverged at call 2:

```
query_aap2 get_job_log -> {"error": "query_aap2 did not respond within 240s.
  The simulated service accepted the request and never answered; treat this as
  the tool being unavailable rather than as a result."}
```

It **never retried**. It re-tried the provisions DB with different columns, hit
the Babylon catalog (also timed out), queried the account pool on a wrong filter
field, then stopped and wrote the user a to-do list ("browse to this URL", "run
this kubectl", `{{choices}}`: "Retry the AAP2 job log query"). Without the
region, `describe_instances` was never called — `unmatched_expected` holds
exactly that one call, and all 5 required answer items plus the count hang off
it.

**Why it didn't retry — the causal link to my own prior edit.** cand_0001 added
to `shared_context.md`:

> ## Unavailable Tools: Pivot, Don't Retry
> If a tool reports that it is **unavailable**, not modelled, not configured, or
> out of scope, that answer will not change on a second attempt.

The timeout error says *"treat this as the tool being **unavailable**."* The
agent applied that rule faithfully to an error it was never meant to cover.
cand_0001 wrote it for the deterministic `query_provisions_db` refusal — still
correct — and accidentally captured transient timeouts too.

**Verified in the runtime, not assumed** (subagent read `sim_backend.py`): the
timeout is a real wall-clock limit (`asyncio.wait_for`, `PARSEC_SIM_TIMEOUT=240`)
on a fresh MCP round trip per call. There is **no fault injection, no seed, no
per-session latch** — a second identical call is a brand-new request and can
return real data. So the retry is a genuine fix, not a hope. Conversely "is not
modelled" comes from a fixed `UNMODELLED` list and is permanent, which is why I
**split** the rule rather than weakening it.

Also verified before editing (this invalidated a draft): the orchestrator loads
**only** `orchestrator.md`; sub-agents load `shared_context.md` + their own
domain file. `query_aap2` belongs to the aap2 sub-agent, `query_aws_account` to
the security sub-agent. Delegation calls are absent from `agent.jsonl`, which is
why the trace *looks* flat — it is not.

## 2. Ranked issues

| # | Issue | Class | Fixed in |
|---|---|---|---|
| 1 | Timeout misread as permanent unavailability → no retry → region never obtained | right domain, wrong action / overcautious | `shared_context.md`, `aap2_agent.md` |
| 2 | Orchestrator treated a timed-out sub-agent report as a finished answer, emitting a to-do list + choices menu | overcautious / outsourcing its own work | `orchestrator.md` |
| 3 | Empty result from filtering on the wrong *field* read as "no such record" | missing knowledge | `shared_context.md` |

## 3. Edits

**`shared_context.md` — replaced "Unavailable Tools: Pivot, Don't Retry" with
"Failed Tool Calls: Refusal vs No-Answer".** Two cases, marker lists, opposite
responses, and an explicit tie-breaker because "unavailable" appears in both:
*if the error reports the service never answered it is case 2 whatever else it
says; a verdict without a timeout is case 1 even if it says "try again".*
Retries bounded ("once"; "only after a second no-answer do you pivot"). Added:
a no-answer must never become a finding about the infrastructure, and must not
be handed to the user as unfinished work.

**Conflicting pre-existing text that would have overridden the new rule** — all
found by adversarial audit; without these the edit was decorative:
- `shared_context.md` "**NEVER call the same tool with the same parameters twice
  in a conversation.**" (absolute, bolded) → carved out the never-answered case
  (no result to reuse ⇒ not a duplicate).
- Babylon-timeout bullet (timeout ⇒ pivot, no retry) and the 429 bullet (⇒ pivot,
  contradicting "rate limited" as a retry marker) → reconciled, plus "never fall
  back to a source that does not carry the fact you need".
- "Report the error and suggest alternatives" → *try* the alternative yourself;
  this sentence licensed the to-do list.
- `aap2_agent.md` "Don't re-fetch job data" → applies only to a call that
  **returned data**; "STOP calling tools and write it NOW / a report with some
  gaps is infinitely better" → one retry first if a needed call timed out.

**`aap2_agent.md`** — at the exact decision point (right after "Always surface
the region you find"): if the job-log call times out, re-issue it once before
anything else, because for a parameter that lives only in the log there is
nothing to pivot to. Only after that retry is the region reported unresolved,
and never as a default or guessed region.

**`orchestrator.md`** — it cannot see `shared_context.md`, so it needs its own
rules: (a) a timed-out region lookup is re-delegated once *before* the inventory
delegation; (b) "A blocked step is not a finished answer" — don't hand over
places *they* could look; (c) gated "After Agent Delegation" on the delegation
having actually answered, because its exhaustive "your only job is to: 1/2/3"
list omitted re-delegating and pushed straight to the menu; (d) the `{{choices}}`
mandate no longer licenses "which source should I retry?".

**`shared_context.md`** (issue 3) — an identifier matched against the wrong
field returns empty for the same reason a wrong scope does: *wrong field*, not
*no such record*.

## 4. Verify the fix

At seed-3's exact divergence (the aap2 sub-agent, having just read the timeout),
the prompt now says *"If the job-log call times out, re-issue it before doing
anything else … Retry the identical call once"*, reinforced by the tie-breaker
that defuses the error's own "treat this as unavailable" wording; and the
duplicate-call ban no longer applies. Every competing instruction a skeptical
audit could find (budget-your-rounds, don't-re-fetch, STOP-and-write-now, the
absolute duplicate ban, the Babylon/429 pivots) now has an explicit carve-out.
A retry returns real data (no latch), giving region → account id →
`describe_instances` → all 5 required items + the count.

At the orchestrator's final turn, the to-do-list/menu output is now explicitly
banned and the section that mandated it is gated on the delegation having
answered.

**Non-overfitting:** `grep` confirms **zero** occurrences of this task's GUID,
sandbox name, account id, region, job id, instance ids or instance types in any
prompt file. Every rule is stated over error *classes* (never-answered vs
verdict) and fires for any tool, domain or parameter.

**Preserved deliberately:** refusal→pivot for `query_provisions_db` "is not
modelled" (verified permanent; the 4 passing trials depend on pivoting off it);
cand_0001's region-before-inventory routing and empty-is-not-absent rules; the
CloudTrail fallback.

## 5. Risk I accepted

Each timeout burns 240s of a 900s agent budget. One retry plus one
re-delegation is bounded but could be tight in the worst case. I bounded every
retry explicitly ("once only", "do not retry it a third time", orchestrator
"once") and ordered it retry-first-then-other-agent, so no unbounded sweep is
licensed. Verbosity rose ~20% on `shared_context.md`; I trimmed three
paragraphs the audit flagged as burying the operative rule.

## 6. Escalation (genuinely out of scope for a prose-only phase)

The underlying defect is environmental: a 240s simulated-service timeout on the
single tool holding a required fact. Prose can only buy one retry. A tools/code
layer should retry transient MCP failures with backoff *below* the agent, so no
prompt needs to encode "retry once" — and so the benchmark measures reasoning
rather than gateway luck.

## 7. Subagents / features used

Fan-out spent on **adversarial review of one edit**, not parallel edits (the run
has one task and one causal chain; parallel edit-worktrees would add merge risk
for no coverage): one read-only subagent on the runtime's fault semantics
(established the retry is sound and the refusal is permanent), one on
prompt-loading (established the orchestrator can't see `shared_context.md`),
two concurrent audits for contradictions and would-this-actually-change-
behaviour, then a final re-audit. The audits changed the edit substantially —
v1 would have lost to the absolute duplicate-call ban and to "After Agent
Delegation".

## 8. What I skipped

No edits to `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
`ocpv_agent.md` — verified never loaded for this task's `services`, so any text
there is dead. No `security_agent.md` change: it already has cand_0001's
region-is-required rule and its lookup never timed out in any trial.
