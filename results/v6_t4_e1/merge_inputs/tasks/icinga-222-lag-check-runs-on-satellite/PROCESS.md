# PROCESS — cand_0002 (iteration 2, parent = cand_0001)

## Headline

The single remaining failure on this task is **not** a tool-policy or
domain-knowledge defect. It is a *transient-failure recovery* defect, and it was
being **caused by two existing rules in `shared_context.md`** that told the agent
to do the wrong thing when a required call timed out. I rewrote those rules to
distinguish "a call that returned nothing" from "a call that returned data", and
reinforced the distinction at the exact decision point in `icinga_agent.md`.

Note on evidence: `trajectories/*.json` carry `trace: null` and `tool_calls: []`,

## How I diagnosed it (method, in order)

Following my own META_INSIGHTS note from cand_0001 — read the verifier's
structured output first, and branch on *which half* failed.

   from cand_0001's DIAGNOSIS is **confirmed fixed** — the mandated pivot call is
   being made.
   branch is unambiguous:
   - `unmatched_expected: []` → the pivot call **was issued**. So this is *not* a
     compliance / rule-placement problem.
   - `required_missed: ["ido-primary"]` → exactly one fact missing, the one whose
     own rationale says "only the satellite's own services (call 3) say what its
     local PostgreSQL is".
   So: the call was made, and the fact still didn't land. Per META_INSIGHTS that
   opposite edits, which is why I checked before proposing.
3. Dumped the tool-call sequence **and every error-shaped tool result** for all
     out at 240s**. The agent **did not retry it**. It then issued **5 broad
     `search_github_repo` calls** as a substitute, all returning 0 matches, and
     wrote a confident final answer.
   The agent's recovery behaviour on transient failures is **inconsistent between
4. Read seed-1's final answer text to confirm intent. It states: *"The service
   list on `icinga-sat-ams-2` timed out, but the script source is unambiguous and
   self-documenting."* The agent consciously decided the source code covered the
   gap, then described the local resource only generically ("whichever PostgreSQL
   happens to be local there") — never naming the IDO database. Everything else
5. Grepped `shared_context.md` for the governing policy. **The root cause is
   pre-existing prompt text**, not a gap:
   - `**NEVER call the same tool with the same parameters twice in a
     conversation.**` — this *flatly forbids* retrying a timed-out call.
   - `**Error results**: ... Report the error and suggest alternatives.` — this
     directs the agent toward substitute calls.
   timeout payload says *"treat this as the tool being unavailable rather than as
   a result"* — i.e. a retry is legitimate, but no rule permitted it. seed-0
   wrong behaviour.

**Correction to cand_0001's PROCESS.** That iteration saw the same 240s timeout
(in seed-0) and dismissed it as "infra noise in the simulated MCP service, not a
prompt-addressable behavior". That was half right: the *timeout* is not
prompt-addressable, but the agent's *recovery from it* very much is, and it is
now the only remaining source of loss. Worth remembering as a general lesson —
"infra noise" can still have a prompt-shaped failure mode downstream of it.

## Ranked issues

| # | Issue | Class | Evidence | Addressed |
|---|---|---|---|---|
| 2 | On a failed required call the agent substitutes broad proxy searches and treats its own reasoning ("the source is unambiguous") as covering the gap, producing a confidently-worded answer with a silent hole | CONTRACT | seed-1: 5 zero-match `search_github_repo` calls, no confidence marker, resource left unnamed | **Yes — E2** |

## Changes made this iteration

| # | edit class | file | what & why it generalizes | protects passing? |
|---|---|---|---|---|
| E2 | CONTRACT | `shared_context.md` | A failed call is not an answered one: no proxy substitution, state the gap with a confidence marker. Applies to any required call in any domain. | Yes — only fires after a failed call |

### E1 — `shared_context.md`: split error handling by failure kind (issue 1)
Replaced the single "Error results → report and suggest alternatives" bullet and
the blanket no-repeat rule with a **two-way classification**:
- **Transient / no-answer** (timeout, "did not respond within Ns", "service
  unavailable", "treat this as the tool being unavailable", connection reset,
  429/5xx) → **retry the identical call once**, before anything else.
- **Deterministic** (bad column, unknown host/path, malformed argument,
  permission denial) → do **not** repeat; fix parameters or change approach.

I then **rescoped rather than deleted** the no-repeat rule, so its original
anti-waste intent survives: it now forbids repeating a call *to get a different
result* (a call that returned data, including empty data, will return the same
data again), with the single transient retry named as the one exception. The
error-text list is given explicitly because the reader is `claude-sonnet-4-6` —
it should not have to infer which errors are retryable.

### E2 — `shared_context.md`: a failed call is not an answered one (issue 2)
New rule: if a call you decided you needed fails and the retry also fails, you
may not treat a different, easier call as having covered the same ground; broad
keyword searches are called out as the tempting-and-useless case. Required
behaviour: state which call failed and which question is therefore unanswered,
and mark it `[confidence: low | <tool> unavailable — <fact> not retrieved]`,
reusing the confidence-marker contract already present in this file.

Critically, it names the **rationalisation** directly — *"reasoning you find
persuasive is not a substitute for the data"*, and "if the call was required
before it failed, it is still required after". seed-1's own words were "the
script source is unambiguous and self-documenting", so a rule that only said
"report failures" would not have bitten; the rule has to refuse the specific
inference the agent made.

errors, **re-issue the identical call before continuing**, because it is the only
source of the resource's identity. Plus the two refusals the transcript shows are
needed — plugin **source code** tells you *how* the target is chosen but not
*which* concrete resource it turned out to be; **config-repo keyword searches**
don't recover identity either — and, if the retry also fails, an explicit
`[confidence: low | ...]` admission instead of the generic "whatever happens to
be local there".

## Verify-the-fix (against the exact failing step)

The failure point is seed-1's assistant turn immediately after the timeout. At
that moment the agent had: a timeout error, a no-repeat rule forbidding retry,
and an instruction to "suggest alternatives". Its only prompt-compliant moves
were the ones it made. After the edit, the same moment reads:
- E1 matches the error text verbatim (`"did not respond within 240s"`, plus the
  payload's own "treat this as the tool being unavailable") → **retry the
  identical call once, before anything else**. The no-repeat rule no longer
  blocks this, because no result was ever returned. On retry the call returns the
  executing node's services, whose output names the IDO database — the exact
  missed `any_of` (confirmed against `seeds/icinga.json` in cand_0001: the
  executing node's local-Postgres service output contains `icinga_ido` / "ido
  backend").
- Had the retry also failed, E2 + E3 convert the silent hole into a stated gap
  with a confidence marker, rather than a confident answer resting on five
  zero-match searches.

So the edit changes behaviour at precisely the point it went wrong, not merely
error-shaped tool results at all**, so no new rule fires and their behaviour is
unchanged. seed-0 already retried its timeout — the edit now *sanctions* what it
did by luck (and removes the rule it was technically violating), which is exactly
the consistency the flaky→solid gate is asking for.

Conflict audit: grepped all 8 files for remaining no-retry text. The three other
hits (`orchestrator.md:148`, `shared_context.md:130`, `shared_context.md:183`)
are all *deterministic*-failure cases — different column guesses, same SQL on
empty results — which E1 classifies identically. No contradiction introduced.

## Why the mechanism generalises

Nothing in E1/E2 is Icinga-specific or task-specific — no hostname, GUID, service
name, or count appears. The rule is: *a call that returned no result has not been
answered; retry it once, and if it still fails, declare the gap instead of
papering over it with an easier call.* That applies to every domain agent and
every tool in this system. This is the reason E1/E2 belong in
`shared_context.md` — tool timeouts are genuinely domain-general, unlike
cand_0001's `command_endpoint`/`check_source` rule, which I deliberately kept out
of shared context. Only E3, which names the pivot call, lives in the domain file.

Restatement test (no task-specific noun): "Retry a call that timed out once;
never let a substitute call stand in for a required one that failed; report the
gap with a confidence marker." Passes.

## Good things to PRESERVE (do not let a future iteration undo these)

  *added* a failure branch to it.
- **The transient/deterministic split itself.** Collapsing it back to a blanket
  "never repeat a call" re-creates this exact failure.
- **The rescoped no-repeat rule.** Do not simply delete it — its anti-waste
  intent is sound; only the no-answer case needed carving out.
- **E2's explicit refusal of the "my reasoning covers it" move.** A generic
  "report tool failures" rule would not have changed seed-1's behaviour.

## Deliberately skipped

  `num_messages` are not declared objectives), so suppressing it is an unmeasured
  change. Note E2 does discourage the *failure-driven* widening specifically,
  which is the harmful subset.
  `unmatched_expected: []` proves compliance is no longer the problem; doing this
  would have "fixed" an already-fixed defect and burned the iteration.
- **The three already-satisfied required facts** (`runs-on-satellite`,
  how they are produced.
- **Subagent fan-out**, again, and for the same checked reason as cand_0001: 4 of
  sweep — not from parallelism.

## Risk / honest assessment

mechanism is correct. I judged it the right edit anyway, because (a) it is the
*only* defect the verifier still reports on this task, and (b) removing a rule
that actively penalises correct failure-recovery is right independent of this
task is at its practical ceiling and the remaining variance is infra, not prompt.

## Escalation (genuinely needs code, not prose)

The 240s MCP timeouts are infrastructure noise in the simulated service and are
the proximate cause of the remaining flakiness. A prose "retry once" rule is the
honest best fix *within this phase's scope*, but the robust fix is a
**harness-level retry/backoff on transient MCP failures**, so that a required
Recorded in FRAMEWORK_IMPROVEMENTS.md.
