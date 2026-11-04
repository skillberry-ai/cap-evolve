# PROCESS — cand_0002 (iteration 2, parent = cand_0001)

## Headline

The single remaining failure on this task is **not** a tool-policy or
domain-knowledge defect. It is a *transient-failure recovery* defect, and it was
being **caused by two existing rules in `shared_context.md`** that told the agent
to do the wrong thing when a required call timed out. I rewrote those rules to
distinguish "a call that returned nothing" from "a call that returned data", and
reinforced the distinction at the exact decision point in `icinga_agent.md`.

Note on evidence: `trajectories/*.json` carry `trace: null` and `tool_calls: []`,
so all evidence below comes from the harbor job dirs named in each trial's
`metadata.trial_dir` (`.../<trial>/agent/agent.jsonl`) plus the per-trial
`verifier/reward-detail.json`.

## How I diagnosed it (method, in order)

Following my own META_INSIGHTS note from cand_0001 — read the verifier's
structured output first, and branch on *which half* failed.

1. Read all 5 `trajectories/*.json`. Scores: **1.0, 0.883, 1.0, 1.0, 1.0**.
   `tool_calls` is now **1.0 in 5/5** (was 0.667 in 10/10 at seed). Cluster A
   from cand_0001's DIAGNOSIS is **confirmed fixed** — the mandated pivot call is
   being made.
2. Read `verifier/reward-detail.json` for the one sub-1.0 trial (seed-1). The
   branch is unambiguous:
   - `unmatched_expected: []` → the pivot call **was issued**. So this is *not* a
     compliance / rule-placement problem.
   - `required_missed: ["ido-primary"]` → exactly one fact missing, the one whose
     own rationale says "only the satellite's own services (call 3) say what its
     local PostgreSQL is".
   So: the call was made, and the fact still didn't land. Per META_INSIGHTS that
   means an *answer/recovery* problem, not a tool problem. These two need
   opposite edits, which is why I checked before proposing.
3. Dumped the tool-call sequence **and every error-shaped tool result** for all
   trials. This is what located the mechanism:
   - **seed-1 (0.883)**: the pivot `get_services` on the executing node **timed
     out at 240s**. The agent **did not retry it**. It then issued **5 broad
     `search_github_repo` calls** as a substitute, all returning 0 matches, and
     wrote a confident final answer.
   - **seed-0 (1.0)**: a *different* call (`fetch_github_file`) timed out — and
     the agent **did retry it**, got the data, and scored 1.0.
   The agent's recovery behaviour on transient failures is **inconsistent between
   trials**. That inconsistency is precisely the flakiness being measured.
4. Read seed-1's final answer text to confirm intent. It states: *"The service
   list on `icinga-sat-ams-2` timed out, but the script source is unambiguous and
   self-documenting."* The agent consciously decided the source code covered the
   gap, then described the local resource only generically ("whichever PostgreSQL
   happens to be local there") — never naming the IDO database. Everything else
   in that answer is excellent; it lost 0.117 solely on the unnamed resource.
5. Grepped `shared_context.md` for the governing policy. **The root cause is
   pre-existing prompt text**, not a gap:
   - `**NEVER call the same tool with the same parameters twice in a
     conversation.**` — this *flatly forbids* retrying a timed-out call.
   - `**Error results**: ... Report the error and suggest alternatives.` — this
     directs the agent toward substitute calls.
   The agent followed both rules exactly as written. Meanwhile the harness's own
   timeout payload says *"treat this as the tool being unavailable rather than as
   a result"* — i.e. a retry is legitimate, but no rule permitted it. seed-0
   scored 1.0 by *violating* the no-repeat rule. The prompt was rewarding the
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
| 1 | Blanket "never call the same tool with the same parameters twice" forbids retrying a call that **never returned a result**; a required fact is then permanently lost to a 240s timeout | BEHAVIORAL (prompt-caused) | seed-1 lost `ido-primary` after the pivot timed out; seed-0 scored 1.0 by retrying | **Yes — E1** |
| 2 | On a failed required call the agent substitutes broad proxy searches and treats its own reasoning ("the source is unambiguous") as covering the gap, producing a confidently-worded answer with a silent hole | CONTRACT | seed-1: 5 zero-match `search_github_repo` calls, no confidence marker, resource left unnamed | **Yes — E2** |
| 3 | Step 0.2 mandates the pivot call but says nothing about what to do if it fails — the strongest "you MUST" in the file has no failure branch | KNOWLEDGE | seed-1 abandoned a step the prompt calls "not optional" | **Yes — E3** |

## Changes made this iteration

| # | edit class | file | what & why it generalizes | protects passing? |
|---|---|---|---|---|
| E1 | BEHAVIORAL / policy | `shared_context.md` | Split error handling into transient-vs-deterministic; retry the identical call once on no-answer failures. Keyed on error *text*, not on any tool or domain. | Yes — only fires on error results; 3/5 trials have none |
| E2 | CONTRACT | `shared_context.md` | A failed call is not an answered one: no proxy substitution, state the gap with a confidence marker. Applies to any required call in any domain. | Yes — only fires after a failed call |
| E3 | KNOWLEDGE | `icinga_agent.md` | Failure branch on Step 0.2's mandatory pivot: retry; don't substitute plugin source or repo searches. | Yes — nested inside an already-gated branch |

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

### E3 — `icinga_agent.md`: failure branch on Step 0.2's mandatory pivot (issue 3)
At the point where Step 0.2 mandates the pivot, added: if the call times out or
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
nearby. Blast-radius check on the passing trials: seeds 2/3/4 had **no
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

- **All of cand_0001's Step 0.2**, unchanged. It demonstrably fixed `tool_calls`
  (0.667 → 1.0 in 5/5) and the `ido-primary` miss rate (9/10 → 1/5). I only
  *added* a failure branch to it.
- **The transient/deterministic split itself.** Collapsing it back to a blanket
  "never repeat a call" re-creates this exact failure.
- **The rescoped no-repeat rule.** Do not simply delete it — its anti-waste
  intent is sound; only the no-answer case needed carving out.
- **E2's explicit refusal of the "my reasoning covers it" move.** A generic
  "report tool failures" rule would not have changed seed-1's behaviour.

## Deliberately skipped

- **The `search_github_repo` waste pattern.** Still unscored (`cost`/`latency`/
  `num_messages` are not declared objectives), so suppressing it is an unmeasured
  change. Note E2 does discourage the *failure-driven* widening specifically,
  which is the harmful subset.
- **Re-tightening Step 0.2's compliance** (fold into Step 0, add a worked-example
  payload — the options cand_0001 queued in case of a reject).
  `unmatched_expected: []` proves compliance is no longer the problem; doing this
  would have "fixed" an already-fixed defect and burned the iteration.
- **The three already-satisfied required facts** (`runs-on-satellite`,
  `local-socket`, `not-in-recovery-zero`) — hit in 5/5; nothing I changed affects
  how they are produced.
- **Subagent fan-out**, again, and for the same checked reason as cand_0001: 4 of
  5 trials are at 1.0 with no error results, so there is exactly one cluster in
  one trial. Fan-out would have bought N copies of one finding. The leverage came
  from dumping error-shaped tool results across *all* trials — a cheap serial
  sweep — not from parallelism.

## Risk / honest assessment

The headroom is small by construction: 4/5 trials already score 1.0, so the
measurable ceiling is ~0.023 val. Whether that clears the significance bar is
genuinely uncertain — this may be rejected for being too small a move even if the
mechanism is correct. I judged it the right edit anyway, because (a) it is the
*only* defect the verifier still reports on this task, and (b) removing a rule
that actively penalises correct failure-recovery is right independent of this
task's score. If it is rejected as insignificant, the honest read is that this
task is at its practical ceiling and the remaining variance is infra, not prompt.

## Escalation (genuinely needs code, not prose)

The 240s MCP timeouts are infrastructure noise in the simulated service and are
the proximate cause of the remaining flakiness. A prose "retry once" rule is the
honest best fix *within this phase's scope*, but the robust fix is a
**harness-level retry/backoff on transient MCP failures**, so that a required
fact is never lost to a tool that "accepted the request and never answered".
Recorded in FRAMEWORK_IMPROVEMENTS.md.
