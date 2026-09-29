# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 1 of 3. No prior iterations existed (`RUNMAP.md`, `LEDGER.md` empty;
`rejected.jsonl` / `history.jsonl` do not exist yet), so nothing here builds on or
avoids a previous candidate.

## First correction to the framing: the task is NOT flaky

`INSTRUCTIONS.md` labels `cloud-024-guid-to-account` as **flaky** ("passes
sometimes"). It does not. I checked every trial of this task that exists on disk:

| run | trials | reward |
| --- | --- | --- |
| `v4_t2_e1` (this run, seeds 0-4) | 5 | 0.2 every time |
| `full34` (2026-09-16) | 3 | 0.2 every time |

8/8 at exactly `{reward 0.2, completion 1.0, tool_calls 0.0, answer 0.25}`, per-task
`stderr` 0.0. The task has **never once passed**. The "flaky" label is an artifact of
0.2 sitting between 0 and 1, not of variance. That reframes the work: this is not
"make good behavior consistent", it is "the good behavior has never happened".

Consequence for the gate: there is ~0.8 of headroom and no noise to speak of, so a
working fix should clear the significance bar easily; a rejected result would mean the
fix genuinely did not fire, not that it was drowned in noise.

## The failure, from the trace

The whole user instruction is a bare 5-character GUID (`instruction.md` is one line,
five characters). In all 5 seeds the orchestrator replied:

> "I didn't quite catch that — could you clarify what you'd like to investigate?"
> followed by a generic `{{choices}}` menu of investigation types

and made **zero** tool calls. Wording drifts between seeds ("what you'd like to
investigate" vs "what you're looking for"; "that." vs "that —") and the string appears
nowhere in the parsec source tree — only in agent transcripts. So it is
model-generated, not a hardcoded short-input guard, and **prose is the right lever**
(the one check that could have made this iteration unfixable-by-prompt).

Scoring arithmetic, confirmed by reading `tests/verify.py`: `answer` is scored over a
denominator of `required + forbidden` = 3 + 1 = 4. The clarify reply satisfies 0
required and trips 0 forbidden → 1/4 = 0.25, and `0.2·0 + 0.8·0.25 = 0.2`. Exactly the
observed number. Each required fact is worth 0.2 of final reward; the tool call is
worth 0.2; a forbidden hit costs 0.2.

## Ranked issue list

One task, one trajectory-group, five identical traces — so one cluster, with three
distinct root causes stacked inside it. All three sit in `orchestrator.md`, which is
the agent that actually failed (it never delegated, so no domain file was reached).

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Bare-token prompt answered with a clarifying question instead of a lookup | cloud-024 (8/8 trials) | The clarify rule has no floor. "If a question is ambiguous … ask the user before running queries" + the top-of-file `MUST use {{choices}}` + "Handle directly when: … Clarifying questions" make asking the cheapest compliant action for a one-token message. Nothing says a message containing a resolvable identifier is actionable. | BEHAVIORAL (over-caution) | narrow an over-strong rule with a discriminating condition (levers 9 + 4) |
| 2 | No route exists from a bare GUID to an account | same | The orchestrator is never told the account-pool rows carry a `guid` field. `query_aws_account_db` is described only as "resolve sandbox names ↔ account IDs"; the only GUID rule present points at Babylon (and is scoped to high-instance-count alerts); `shared_context.md` points 5-char codes at the provisions DB. So even a willing orchestrator has no documented path GUID → sandbox/owner/account. | KNOWLEDGE | add a sourced rule (lever 4) |
| 3 | No output contract for an identify-request, and no exact-row rule | same (latent — never reached, because of #1) | The tool returns the whole table for local filtering. Adjacent pool rows are near-identical (sequential names and account ids; the neighbour of an in-use sandbox is an idle one with no owner). All 8 of the verifier's forbidden forms are about attaching the GUID to the neighbouring row or its state. Nothing tells the orchestrator which facts an identity answer must state. | KNOWLEDGE + contract | tighten the output contract (lever 8) + one worked example (lever 5) |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | narrow an over-strong rule | `orchestrator.md` → "Asking Clarifying Questions" | Rewrote the trigger: ask when the message names **no resolvable entity and no action**, or when it forks two materially different expensive investigations. Kept the original rationale (don't run several costly queries that answer the wrong question) but scoped it to that case, and added the floor: a message containing a recognizable identifier is always actionable — resolve, *then* ask which follow-up; "short" is not ambiguity; one argument-free lookup is not the expensive-query risk the rule guards. | Yes — the rule still fires for genuinely under-specified prompts. It narrows *when* to ask, and never removes the ability to ask. |
| 1 | resolve a conflict, don't stack | `orchestrator.md` → "Handle directly when", "High instance count / sandbox warnings" | Added "A message that is a bare identifier — resolve it, don't ask what it means" adjacent to the "Clarifying questions" line that licensed the failure, and **rewrote that line itself** — it now reads "Clarifying questions — but only *after* the one cheap lookup that identifies what the user named, never instead of it", so the list no longer licenses the failure two lines from where it forbids it. Also scoped the existing GUID→Babylon rule to the alert path it was written for, pointing a context-free GUID at the account pool. | Yes — the Babylon rule keeps its original verdict on its original input (a GUID arriving from a sandbox warning); clarifying questions are still a legitimate direct-handle action. |
| 1 | narrow an over-strong rule at its most salient point | `orchestrator.md` → the top-of-file `{{choices}}` **IMPORTANT** block | That block is the first instruction in the file and the only one in bold caps; it primes "ask with buttons" before any routing rule is read, and the failing reply was exactly a `{{choices}}` menu. Added one clause: the rule "governs **how** you ask, never **whether** to ask… a message you can resolve with one lookup should be resolved, not turned into a menu", with a pointer to the new section. | Yes — the `{{choices}}` requirement itself is untouched; only the inference "therefore asking is safe" is blocked. |
| 2 | add a sourced rule | `orchestrator.md` → Direct Tools bullet | `query_aws_account_db` also resolves GUID → sandbox/owner/account because every pool row carries a `guid` field. States that there is **no `guid` parameter**, lists the filters that do exist, and gives the correct narrowing: a row carrying a `guid` is by definition in use → `available: false` + raised `max_results`, exact-match the `guid` locally, and narrow further if `truncated: true`. | Yes — additive; the existing name↔id use is unchanged. |
| 2 | add a sourced rule | `orchestrator.md` → new "Bare Identifiers and Minimal Prompts", Step 1 | A shape→lookup table covering 7 identifier shapes (5-char GUID, `sandboxNNNN`, 12-digit account id, `pool-XX-NNN`, `sandbox-<guid>-zt-*`, email, Babylon URL/workshop name), plus "handle the resolution directly; delegate only for the follow-up the user picks", plus the fallback when the shape is unrecognized (quote the token, name the shapes you can resolve — not a generic menu). | Yes — every row reuses a mapping already asserted elsewhere in the prompt set; none of them changes an existing verdict. |
| 3 | tighten the output contract | `orchestrator.md` → Step 2 + Step 3 | Step 2: select the row whose field is an **exact, full-string match**; never the first row; never prefix/substring-match; if nothing matches exactly say the identifier is not in the pool rather than presenting the closest row; report **only** the matched row and do not describe rows you filtered out; describe state with the row's own field values rather than by negating the opposite state. Step 3: state what the token is, the entity it belongs to, who holds it, and the actionable id — all from the matched row — then one short context paragraph, then offer the follow-ups as `{{choices}}` instead of chasing them. | Yes — nothing here loosens a rule. It reinforces the existing "Stay Focused on the Current Investigation" section rather than competing with it. |
| 3 | add one example | `orchestrator.md` → `<example>` block | One compact worked example: a bare token, the argument-free call, two returned rows, which row is selected **and why** (the non-matching row is first and has an empty `guid`; the matching row is second), and the resulting answer + `{{choices}}`. Closes with "identifiers above are illustrative — always report values from your own tool result." | Yes — additive. |
| 2 | resolve a conflict | `shared_context.md` → "Route lookups by identifier shape" | The old bullet sent all 5-char codes to `provisions` by `babylon_guid`, which is the wrong source for "what is this GUID". Split by question: *identity / which sandbox and account* → `query_aws_account_db` (rows carry `guid`, no required args, exact-match the row); *provision history / user / catalog item / timestamps* → `provisions` by `babylon_guid`. | Yes — the original instruction survives verbatim for the question it was written for; this adds the missing direction rather than replacing it. |

## Verify-the-fix

Each line: the exact point in the trace that went wrong → what the new text does at
that point.

- **Trace point: the orchestrator receives a 5-char message and emits "I didn't quite
  catch that" + generic menu, 0 tool calls.** The new "Bare Identifiers and Minimal
  Prompts" section sits at line 111 — before Routing Guidelines, and ~190 lines before
  the clarify section — and its second paragraph prohibits exactly this reply in the
  words the trace used: "Never answer such a message with 'I didn't catch that' or with
  a generic menu of investigation types." Step 1's table then matches the token's shape
  and names the call. This is the one edit that had to fire; everything else is
  downstream of it.
- **The predicate that decides whether any of the above fires — checked character by
  character, because the first draft got it wrong.** That table row originally read
  "5 characters, lowercase letters + digits". The real token is 5 lowercase letters with
  **zero digits**; read as a conjunction that row does not match it, control falls to
  "if the token matches none of these shapes, then ask", and the candidate reproduces the
  original failure with better wording and still 0 tool calls. Every 5-char exemplar in
  all 8 baseline files contains a digit (`w4t8r`, `ghx5c`, `2t7js`, `2vvct`, `m7hff`,
  `z486v`, `zz7zn`), so nothing anywhere taught that an all-letter code is a GUID. The
  row now states the character class explicitly ("each one a lowercase letter **or** a
  digit. Digits are optional") with an all-letter exemplar, and `shared_context.md` got
  the same treatment. Verified: `re.fullmatch(r"[a-z0-9]{5}", <the token>)` matches.
- **Trace point: the clarify rule made asking the compliant choice.** The rewritten
  "Asking Clarifying Questions" no longer licenses it — "'The message is short' is not
  ambiguity", and the expensive-query rationale is explicitly scoped so it cannot be
  read to cover a single argument-free lookup. So the two sections now give the *same*
  verdict on this input instead of opposite ones.
- **Trace point: never reached — no tool call, so no row selection.** Verified against
  the seeded data instead: the pool returns two rows, one in-use with the GUID in its
  `guid` field and one idle with an empty `guid` and a neighbouring account id. Step 2's
  exact-full-string-match-on-`guid` rule selects the first and rejects the second
  (empty `guid` cannot exact-match a 5-char token); the example demonstrates precisely
  that rejection. Step 3 then requires the entity name, the owner, and the account id —
  the three values the verifier checks.
- **Forbidden-form protection, verified against `verify.py` semantics.** The forbidden
  check is per-sentence substring with no `attributed_to` exemption for this task, so a
  single sentence like "the neighbouring sandbox is available" is a violation worth 0.2
  of reward. Step 2's "report only the row you matched; do not describe the rows you
  filtered out" is what prevents that sentence from being written. This is also the
  honest rule independent of the scorer — it is the same instruction the existing "Stay
  Focused on the Current Investigation" section already gives for entities.
- **Mechanical check that the new prose cannot leak the answer or seed a forbidden
  phrase.** Scripted scan of both edited files: zero occurrences of any of the 8
  forbidden substrings, and zero occurrences of the task's literals (`jbfsq`,
  `sandbox2291`, `sandbox2292`, `rrivers`, `419283746501`, `419283746502`). The
  example deliberately uses structurally distant invented values and says so. I also
  avoided the words "is unassigned" / "is available" as connected phrases anywhere in
  the new text, since planting them raises the chance the reader echoes them.
- **Tool-call component.** Read `_call_matches` in `verify.py`: an expected `args: {}`
  imposes no key constraints, so any `query_aws_account_db` call scores the full 0.2,
  narrowed or not. That freedom is what let me write the *honest* call rather than the
  seed-shaped one — see the next bullet.
- **Corrected a claim that was true of the seed and false of the tool.** The first draft
  told the reader the tool "takes no required arguments — call it with none and filter
  the returned rows yourself". I then read the real implementation
  (`parsec-live/src/tools/aws_accounts.py:145`): the signature is
  `(name, account_id, available, owner, zone, envtype, reservation, max_results)` —
  there is **no `guid` parameter**, `DEFAULT_MAX_RESULTS = 100`, `MAX_RESULTS_CAP = 500`,
  and the response carries `count` + `truncated`. So "call it bare and filter locally"
  works only because this seed's pool has **2 rows**; against the real pool it would
  scan the first 100 of thousands and silently conclude a GUID is absent. The rule now
  states the missing parameter, and gives the narrowing that follows from the data model
  rather than from the seed: a row carrying a `guid` is by definition in use, so
  `available: false` + a raised `max_results`, exact-match locally, and narrow further
  if `truncated: true`. Checked against `seeds/cloud.json`: the matching row is
  `available: false`, so the narrowed call returns it. This also turns out to be
  **score-protective, not just honest** — if the backend honors the filter, the idle
  neighbouring row, which is the only realistic source of all 8 forbidden forms (its
  `conan_status` is literally the string `available`), never enters the context window.

## Process & features used

- **Subagents:** one background adversarial-audit subagent, briefed with the verifier
  contract and asked to attack the edit on six axes (would it still not fire; forbidden
  phrase hazards in the new text; echo risk from the worked example; contradictions
  across all 8 files; overfit; dropped constraints). I deliberately did **not** fan out
  one diagnostic subagent per trajectory-group as `INSTRUCTIONS.md` suggests: there is
  exactly one task with five byte-identical outcomes, so there is one group and
  parallel diagnosis would have produced five copies of the same finding. The honest
  use of parallelism here was verification, not diagnosis. No worktrees — the edits
  touch two files in one coherent change, so there was nothing to merge.
- **The audit was the highest-value step of the iteration and it changed the candidate.**
  It returned 8 findings against what I already considered finished, of which three were
  real defects I had missed and would not have found by re-reading my own diff:
  1. *The gate predicate excluded the actual input* (the letters+digits conjunction). This
     was the whole candidate: had it shipped, the most likely RESULT was a rejection at
     `tool_calls 0.0` that looked like "prose does not work on this failure" — the wrong
     lesson, banked in the LEDGER for two more iterations.
  2. *A factual claim about the tool that was true only of a 2-row seed.* Fixing it cost
     nothing at the gate and removed a win-for-the-wrong-reason.
  3. *A stated root cause left un-edited* — I had named the "Clarifying questions" bullet
     as root cause #1 in this very file and then added a contradicting line two lines
     above it instead of fixing it.
  I verified each of the three against primary sources before acting (the real tool
  source, the seed file, and a regex check on the character class) rather than taking the
  audit's word for them; the remaining five findings I judged and took four of: the
  primacy clause on the `{{choices}}` block, the example's `owner_email` column, the
  example's missing `Sources:` footer, and rephrasing a seed-derived generalisation as the
  ownership invariant. The one I declined: editing `babylon_agent.md`, whose GUID rule is
  correct inside its own domain — I scoped the claim in `shared_context.md` instead, which
  keeps the diff at two files.
- **Lesson for the remaining iterations, stated plainly:** at n=1 with a deterministic
  failure, an adversarial pass over the *finished* candidate is worth more than any amount
  of additional diagnosis, because the dominant risk is not misdiagnosis — the trace makes
  the diagnosis obvious — it is an edit that is correct in intent and does not fire.
- **Prior iterations read:** none exist. `RUNMAP.md` and `LEDGER.md` are empty
  templates and `rejected.jsonl` / `history.jsonl` are absent, so there were no refuted
  approaches to avoid. Both facts are recorded in `JOURNAL.md` for iteration 2.
- **Reader tier:** declared `claude-sonnet-4-6`, "strong". I followed the guidance's
  strong-reader advice (give the reason with each rule, keep exemplars minimal — one
  example, not a set) but took `INSTRUCTIONS.md`'s "add a worked example for tricky
  formats" for the row-selection step specifically, because near-identical-neighbour
  selection is the one behavior here that prose describes poorly.
- **Length:** `orchestrator.md` 246 → 383 lines, `shared_context.md` 238 → 251. That
  is real growth and it is the thing iteration 2 should watch. I judged it worth it for
  a class that has never passed once and had three independent gaps; if the gate accepts
  this, the example block (~30 lines) is the first candidate for pruning to test whether
  the prose rules carry it alone.

## Good things to PRESERVE (do not let a future iteration undo these)

- **The discriminating condition is "the entire message is one identifier-shaped token
  with no verb and no question."** Do not widen this to "short messages" or "messages
  containing an identifier" — a real question that happens to contain a GUID must keep
  going to the routing rules, not to the identity contract.
- **The clarify rule still exists.** It was narrowed, not deleted. Do not remove the
  ability to ask; the unrecognized-shape fallback is what keeps the section honest.
- **"Report only the row you matched."** Worth 0.2 of reward here and correct
  independent of the scorer. Do not "improve" the answer by having it describe the
  other pool rows for completeness.
- **The example's matching row is deliberately the SECOND row.** That forces the reader
  to rely on the field match rather than on position. In this task's seeded data the
  answer happens to be the first row, so an example that matched row 1 would teach the
  wrong invariant and pass for the wrong reason.
- **Both rows in the example are in use, and differ by one character.** The first draft
  distinguished them by one having an empty `guid`, which is the easy case and is the
  seed's own shape. Two in-use near-identical neighbours is the harder discrimination and
  the one the narrowed query actually returns. The empty-`guid` fact now lives in Step 2
  as the stated invariant instead of being smuggled in through the example.
- **Every value in the example is visibly read off a column**, including `owner_email`.
  An earlier draft printed `dpatel@example.com` while showing no email column, which
  teaches deriving an address from an owner name — the pool's real emails do not follow
  that pattern (the seed's owner `rrivers` maps to an address on a different domain).
- **No task literal appears in any prompt file.** Keep it that way; re-run the scan in
  the Verify-the-fix section after any edit to these sections.

## Deliberately skipped

- **The other 5 domain agent files** (`aap2`, `babylon`, `icinga`, `ocpv`, `security`,
  and `cost` beyond leaving it untouched). The orchestrator never delegated, so none of
  them was in the trace's causal path. `cost_agent.md` already documents the pool's
  `guid` field at line 183, so the knowledge gap was specifically the orchestrator's,
  not the cost agent's. Editing them would have been prose-where-the-failure-wasn't —
  the guidance's named most-expensive wasted iteration.
- **Cross-task generalization.** `train`/`val`/`test` are the same single task this
  round, so there is no held-out task to protect. I still wrote every rule as a pattern
  rather than a case, because the gate re-scores on the same task with different seeds
  and because iteration 2 may inherit these files into a wider run.

## Escalation (capability gap, not fixable by prose — for the record)

**There is a real capability gap here, and prose can only paper over it.** I originally
wrote "nothing in this cluster needed a new tool". Reading the implementation
(`parsec-live/src/tools/aws_accounts.py:145`) falsified that:

> `query_aws_account_db(name, account_id, available, owner, zone, envtype, reservation,
> max_results)` — **no `guid` parameter**, `DEFAULT_MAX_RESULTS = 100`,
> `MAX_RESULTS_CAP = 500`.

So GUID → account is *not* a supported query. It is a client-side scan over a page of a
pool that holds thousands of accounts, and the hard cap of 500 means **the lookup this
task asks for cannot be guaranteed to succeed at all** on the real pool: if the GUID's
row falls outside the returned page, the only correct answer is "I could not determine
that", and no wording in any prompt file changes it. This task passes on the seed because
the seeded pool has 2 rows. The best prose can do — and what I did — is make the reader
narrow with `available: false`, raise `max_results`, and respect `truncated: true` instead
of concluding absence from a truncated page. **Ask for the tools layer:** add a `guid`
filter to `query_aws_account_db` (the field is already returned and is effectively unique,
so it is a filter expression on an existing attribute, or better a GSI), and until then
have the tool surface `truncated` prominently enough that a partial scan cannot be
mistaken for a complete one. A second, smaller weakness: **the shape→lookup mapping is
duplicated prose in two files that can drift** —
`orchestrator.md`'s new table and `shared_context.md`'s identifier-shape bullet now
assert overlapping mappings. A tools-layer round could collapse both into a single
`resolve_identifier(token)` composite that dispatches on shape and returns the matched
row, which would make the exact-match rule code-enforced instead of prose the reader
has to remember. That is a genuine improvement but out of this phase's scope.
