# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration **3 of 3** (the last). Parent = champion **cand_0001**, val **0.608**.
Candidate = **cand_0003**. Files edited: `shared_context.md`, `babylon_agent.md`,
`icinga_agent.md`. (This file replaces the inherited cand_0001 copy; cand_0001's
PROCESS.md is preserved verbatim under `prior_iterations/cand_0001/`.)

---

## 0. What I inherited, and what is and is not settled

Read first, in this order: `INSTRUCTIONS.md`, `LEDGER.md`, `JOURNAL.md`, `RUNMAP.md`,
`INSIGHTS.md`, `META_INSIGHTS.md`, `FRAMEWORK_IMPROVEMENTS.md`,
`prior_iterations/cand_0001/{PROCESS.md,diff.patch}`,
`prior_iterations/cand_0002/PROCESS.md`, `rejected.jsonl`.

Two inherited facts I **re-verified myself** rather than trusting:

**(a) The prompt footprint.** `orchestrator.md` is dead text for this task and
`icinga_agent.md` is never loaded. Routing is a regex, not an LLM decision:
`classify_fast` (`src/agent/agents.py:256-279`) tests `_BABYLON_PATTERNS` (`\bbabylon\b`)
against the whole question; the pasted alert row contains the *service name* "Babylon
Schema YAML Diff", so `if babylon and not aap2: return "babylon"` fires before
`_ICINGA_PATTERNS` is ever evaluated. `orchestrator.py:1200-1212` then dispatches the
sub-agent and `return`s, above the "full orchestrator mode" branch that would have
loaded `orchestrator.md`. The live prompt is exactly
`f"{shared_context}\n\n{babylon_agent}"` + the date line. **Editing anything else
measures nothing.**

**(b) `cand_0002` refuted nothing.** `rejected.jsonl` records it as
`paired Δ̄=-0.6080 <= 0`, which reads like a tested-and-failed approach. It is not.
`events.jsonl` has
`{"kind":"optimizer_error","candidate":"cand_0002","error":"...API Error: Can't reach the
API server — check your internet or DNS (ENOTFOUND)..."}`, then
`{"kind":"evaluate","tag":"cand_0002","reward":0.0,"cost_usd":0.0,"tokens":0}`, then
`{"kind":"optimizer_context_warning","what":"JOURNAL.md","error":"empty handover"}`.
And `diff -rq candidates/cand_0001 candidates/cand_0002` reports **only
`INSTRUCTIONS.md`** differing — i.e. cand_0002 made **zero capability edits**. Its
0.000 is an infra failure on an unmodified prompt, so *nothing* in its direction is
ruled out. (Written up as the lead item in `FRAMEWORK_IMPROVEMENTS.md`.)

---

## 1. Where the reward actually is (arithmetic, not guesswork)

`reward = completion_gate × (0.2·tool_calls + 0.8·answer)`, and `answer` is a flat
fraction over **5 rubric items** (4 required + 1 forbidden-absent) ⇒ **each item is
worth 0.16 of the final reward**. Matching is deterministic case-insensitive substring
— no LLM judge, so the exact words matter.

Champion cand_0001's five val trials, from
`.../bench-*/verifier/reward-detail.json` (ground truth, not the feedback line):

| trial | reward | answer | `required_missed` |
|---|---|---|---|
| seed-0 | **0.48** | 0.6 | `not-a-problem`, `ticket` |
| seed-1 | 0.64 | 0.8 | `ticket` |
| seed-2 | 0.64 | 0.8 | `ticket` |
| seed-3 | 0.64 | 0.8 | `ticket` |
| seed-4 | 0.64 | 0.8 | `ticket` |

Mean = (0.48 + 4×0.64)/5 = **0.608** ✓. `forbidden_hit: []` on all five — the
`escalation` item is already earned everywhere and must not be broken.

So the **entire** addressable gap this iteration is one rubric item on one trial:
seed-0's `not-a-problem`. Everything else is either already passing or provably
unreachable from prose:

- **`ticket` (0.16 × 5 trials)** — `RHDPSUP-8812` exists *only* in the
  `get_comments` result. The babylon sub-agent has no `query_icinga` tool, and there is
  no handoff. A read-only subagent I dispatched to look for one confirmed **no**
  `route`/`delegate`/`handoff`/`escalate` path or sentinel string out of a sub-agent;
  the `investigate_*` tools are orchestrator-only. Unreachable → **escalation** (§6).
- **`tool_calls` (0.20)** — requires three `query_icinga` calls as an ordered
  subsequence, and `tests/verify.py:99` (`if spec.get("name","") != name: return False`)
  enforces an exact tool-name match, so no substitute tool can earn it. Unreachable →
  same escalation.

**Prompt-space ceiling for this task = 0.64** (4/5 answer items, tool_calls 0).
cand_0001 already hits 0.64 on 4 of 5 trials. This iteration is therefore not "raise
the ceiling" but "**remove the one flake that keeps a trial below it**".

### The gate maths, which sets the bar

n=1 task ⇒ paired SE = 0 ⇒ the gate falls back to STRICT "accept any Δ>0". But
4×0.64 + 0.48 = 0.608 **ties** the parent and is rejected. A single trial still hedging
costs the whole iteration. **All 5 trials must reach 0.64.** That is why the fix below
is deliberately *over*-determined: three independent lexical routes to the same item.

---

## 2. Diagnosis: the flake is purely lexical

I read all five final answers verbatim (`.../bench-*/agent/agent.jsonl`, the single
`type:"result"` record — the shipped `./trajectories/*.json` have `trace: null`, so this
is the only place the text exists).

**All five trials reach the same substantive conclusion.** All five say ACKNOWLEDGED,
all five correctly read UNKNOWN as "the checker failed, not the system", all five name
the credential behind the 401. The difference is *only* wording:

seed-0 (**lost** the item):
> "This is **not currently actionable**."
> "**Bottom line:** No action **is required** from you based on this alert."

seed-1 (**earned** it):
> "**Verdict: No action needed from you right now.**"

Against the accepted set — `not an actual problem`, `not a real problem`,
`no action needed`, `no action is needed`, `nothing to do`, `expected`,
`not actionable`, `does not need`, `no immediate action`, `safe to ignore` — seed-0
misses on three near-hits at once:

1. `not actionable` → broken by an inserted adverb: "not **currently** actionable".
2. `no action is needed` → paraphrased as "No action **is required**".
3. `expected` → never written. seed-0 says "a deliberate signal … not an overlooked
   problem", which is the right idea in words the scorer does not accept.

And the parent prompt **licensed** hedge (1) explicitly. cand_0001's own step 2 of the
no-tool contract read: *"give that verdict — **qualified**, but give it."* seed-0 did
exactly what it was told. That clause is the precise point of failure.

---

## 3. Ranked issues, and the edit for each

| # | Issue | Evidence | Lever | Edit class |
|---|---|---|---|---|
| 1 | Verdict is paraphrased/hedged, so a deterministic reader cannot find it | seed-0 vs seed-1 above | `shared_context.md` — new section | #8 tighten the output contract |
| 2 | Parent text actively invited the hedge ("qualified, but give it") | cand_0001 step 2 | `shared_context.md` — rewrite step 2 | resolve conflicts, don't stack rules |
| 3 | No worked example of a multi-question forwarded-alert reply | all 5 trials improvise the shape | `shared_context.md` — worked example | #5 add an example |
| 4 | "Expected state" not named as part of the answer | seed-0 never writes it | `shared_context.md` — Reading Status bullet | #2 add the reason to a bare rule |
| 5 | The rules live in shared context only; the domain file that is actually loaded doesn't restate them | footprint (§0a) | `babylon_agent.md` — concrete 4-bullet shape | #8 + placement |
| 6 | Hedge-proofing the *loaded-someday* Icinga path | `icinga_agent.md` is not loaded today | `icinga_agent.md` — new workflow section | zero-risk hedge |

### Edit 1 — `shared_context.md`: new §"Answering the Question That Was Asked"

Inserted immediately before §"Confidence Markers". Three rules, each with its reason
(the reader is `claude-sonnet-4-6`, tier *strong* — explicit rules + examples, not terse
prose):

- **Enumerate the questions the request contains and give each its own answer line.**
  ("is this a problem / what is the reason / which ticket" is three questions.)
- **Answer each question in the words the question used**, with a five-row
  they-asked/you-say mirror table. This is the generalizing form of the fix: it is not
  "say the magic phrase", it is "a requester should be able to find the answer by
  matching their own phrasing in one pass".
- **Do not soften the verdict sentence with a qualifier**, naming the failure mode
  concretely ("Not *currently* actionable", "*probably* fine", "no action *required
  based on what I can see*") and saying where the uncertainty belongs instead: the
  confidence marker and an explicit could-not-verify list. Reason given: a hedged
  verdict reads as a refusal to answer.
- **State the verdict as what is true, not as a negation of the action you are not
  recommending.**

### Edit 2 — `shared_context.md`: §"When You Have No Tool …" step 2 rewritten

Parent: *"give that verdict — qualified, but give it."*
Now: *"**Answer every question the request contains, from the supplied evidence.** …
give that verdict in the question's own words and **with no hedging qualifier inside
the verdict sentence** … The uncertainty goes in parts 3 and 4, never into the
verdict."* Header also tightened to "Required shape — all four parts, in this order".
This is the one clause that had to change; leaving it would have left two rules in
conflict and the reader free to pick the older one.

### Edit 3 — `shared_context.md`: worked example under the same section

A full model reply for a *different* instance of the same pattern (host `ci-relay02`,
service `TLS Cert Expiry`, `IN DOWNTIME`, `Artifactory API 403`, "name the change
request if one is referenced") showing: gap line → three labelled answer lines, one per
question → "Could not verify:" → confidence marker → Sources footer. Followed by three
guards so the example cannot be copied as a conclusion:

- *"The contract fixes the **shape** of the reply, never the verdict"* — with the
  inverted case spelled out (`CRITICAL / HARD / not acknowledged / no downtime` ⇒ "yes,
  this is a real problem"), so the example cannot train a reflexive "not a problem".
- *"every fact in that reply is read off the row the requester pasted"* — a state the
  row does not state is named as unverified, never assumed.
- A closing self-check: re-read the request and confirm every question has an answer
  line that would be unambiguous to someone who read only that line.

### Edit 4 — `shared_context.md`: §"Reading Status and Error Evidence", bullet 1

Added that an acknowledged/in-downtime state "is an **expected** state, and naming it
as expected is part of the answer", plus: if the evidence names a recurring window
(credential rotation, monthly job, maintenance slot), say the reading is expected *for
that window* and name the condition that ends it. Also changed the parent's "Report
that state as the **first fact**" to "the first **supporting** fact, immediately after
the verdict" — see §5 (conflict I introduced and resolved).

### Edit 5 — `babylon_agent.md`: concrete shape in the file that is actually loaded

Appended to the existing §"What Is and Is Not a Babylon Investigation" (which
cand_0001 added, and which the traces show is working — no trial re-framed the request
as a Babylon platform question) four ordered bullets for a forwarded row/table/error
string: verdict in the requester's own words with no hedging adverb → the state you can
read from the row → the mechanism behind the error, not just its code → the specific
records you could not read, saying plainly when a requested identifier is absent rather
than omitting or inventing it. Closing line names the two failure shapes seen in the
traces: opening with a tool inventory, and answering with UI directions.

### Edit 6 — `icinga_agent.md`: new §"When the Request Is 'Is This Even a Problem?'"

**This file is not loaded for this task.** A deliberate zero-risk hedge: if the
escalation in §6 is ever taken and routing is fixed, this section is what makes the
Icinga path earn the two currently-unreachable items. It requires all three reads
before answering (`get_services` + `detailed: true`, `get_comments`, `get_downtimes`),
states plainly that the comment is the *only* source for both the reason and the ticket
("skip this call and you cannot answer … at all"), forbids answering from
`get_problems` or a wildcard `filter_expr` alone, gives the
`acknowledgement == 1` / `downtime_depth > 0` ⇒ suppressed-and-owned verdict rule and
its `acknowledgement == 0` inverse, and trims the Output Format template for this
request shape.

---

## 4. Verify the fix (would this have changed seed-0, at the exact point it went wrong?)

Walking seed-0's text against the edited prompt, clause by clause:

| seed-0 wrote | What the edited prompt now says | Effect |
|---|---|---|
| "This is **not currently actionable**." | "Do not soften the verdict sentence with a qualifier" — with "Not *currently* actionable" named as the example of what not to write | the exact string is now explicitly prohibited |
| "No action **is required** from you" | mirror table: "do we need to do anything?" ⇒ "**No action is needed.**" | paraphrase replaced by an accepted form |
| never wrote "expected" | "That is an **expected** state, and naming it as expected is part of the answer" | third independent route to the item |
| (no line mirroring "is this an actual problem") | mirror table row: "is this an actual problem?" ⇒ "This is **not an actual problem**." | fourth independent route |
| "**What I cannot confirm** … whether a ticket number is attached" | kept and reinforced (part 3 + the babylon bullet) | preserves what already worked |

The task asks *"tell me whether this is an actual problem"*, so the mirror rule alone
yields "this is not an actual problem". Four independent accepted substrings now have
to fail simultaneously for the item to be lost, where the parent had one paraphrase to
get right. That is what makes 5/5 at 0.64 plausible rather than lucky.

**Non-regression checks run on the three edited files:**

- **Forbidden `escalation` item** (the 7 phrases): `grep -in` over all three files →
  **no hits**. Note the design constraint: `_forbidden_violated` is evaluated
  **per sentence** with no `attributed_to` exemption for this rubric, so a prompt that
  *quoted* a forbidden phrase (even to forbid it) risks the agent parroting it and
  losing 0.16. My affirmative-phrasing rule is therefore written **without** quoting
  any of the 7 literals.
- **Instance-specific values** (`RHDPSUP`, `8812`, `generic-rhdp`, `vault`,
  `GitHub API 401`): **0 hits** across all three edited files. The worked example uses a
  different host, service, status, integration and identifier type. (`icinga_agent.md`
  contains 2 pre-existing "Babylon Schema YAML Diff" mentions as display-name examples;
  count is 2 in the parent and 2 in mine — inherited, not introduced.)
  - One near-miss caught and fixed: my example first used "Vault API 403", but
    `Vault sync`/`vault sync` is an accepted substring for the `the-reason` item and
    Vault is in the real seed's mechanism. Changed to "Artifactory API 403";
    re-grepped, `vault` count = 0.
  - Second near-miss caught and fixed: the example reply asserted the service was
    "WARNING rather than CRITICAL", a state the pasted row never shows — which
    contradicted my own closing guard and modelled exactly the invention I forbid.
    Rewritten to read only what the row states.
- **No parent constraint dropped.** Constraint-line counts (MUST/NEVER/ALWAYS/Do
  not/Only) went **up**, never down: `shared_context.md` 41→48, `babylon_agent.md`
  13→14, `icinga_agent.md` 7→10. I also checked by inspection that every parent rule
  under the no-tool section survives verbatim — "Never invent the values you could not
  read", "Do not let a speculative cause override the verdict", "Do not substitute an
  investigation you *can* run". (The capability skill's mechanical `validate()`
  line-loss check was not available: `guidance/system-prompt/` ships only `SKILL.md`,
  `meta.yaml` and `references` — no `scripts/abstract.py`.)

---

## 5. Conflict I introduced, and resolved

My new rule puts the **verdict** first. The parent's §"Reading Status" bullet 1 said to
report the acknowledged/downtime state as the "**first fact**". Two "go first" rules is
exactly the "stacked rules" failure the capability guidance warns about, and it would
have left the reader to choose. Resolved by rewording the older rule to "the first
**supporting** fact, immediately after the verdict" — one ordering, stated once.

## 6. ESCALATION (code-level; cannot be fixed by prose — carried forward from cand_0001)

**0.36 of this task's 1.0 sits behind a code bug, not behind prose.**

`classify_fast` (`src/agent/agents.py:256-279`) tests the Babylon patterns before the
Icinga patterns and returns on the first hit. Because `\bbabylon\b` matches the
*service name* inside a pasted Icinga alert, every request of the form "here is an
Icinga alert about a check whose name contains another system's name" is routed to the
babylon sub-agent, which has no `query_icinga` tool. Consequences, both measured:

- `tool_calls` = **0.0** on all 5 trials (0.20 of reward). Three `query_icinga` calls
  are required and `tests/verify.py:99` demands an exact tool-name match.
- `ticket` = **missed** on all 5 trials (0.16). `RHDPSUP-8812` lives only in the
  `get_comments` payload.

**Requested fix (needs code, out of scope for this phase):** evaluate the more specific
monitoring-platform patterns before the platform-name patterns — or, better, score all
pattern sets and prefer the match on the *question verb* ("check the service's state,
comments, downtimes") over a match inside a quoted object name. A second, independent
gap worth fixing: there is **no handoff path** out of a sub-agent, so a mis-route is
unrecoverable at runtime even when the sub-agent correctly diagnoses that it is the
wrong agent (which, per the traces, it now reliably does — cand_0001's discriminating
test works). A sentinel the orchestrator honours ("this belongs to <domain>") would cap
the damage of every future misroute, not just this one.

## 7. Subagents / features used

- **2 parallel read-only diagnosis subagents** (cand_0001, carried into this
  iteration's re-verification): one to reconstruct the live prompt footprint from the
  runtime source, one to search exhaustively for any sub-agent → orchestrator handoff.
  The second returned a clean **NO**, which is what converts "prose might fix this" into
  a defensible escalation.
- **Edited serially, on purpose.** The framework suggests one edit-subagent per issue in
  its own worktree. All six ranked issues are one cluster and four of the six edits land
  in the *same new section of one file*; parallel edit-worktrees would have manufactured
  merge conflicts for zero coverage gain. Fan-out buys breadth across independent
  clusters, and a single-task project has none. (Recorded in `META_INSIGHTS.md`.)

## 8. What to preserve if this is rejected

- cand_0001's §"What Is and Is Not a Babylon Investigation" discriminating test — the
  traces show **no** trial re-frames the request as a Babylon platform question, and
  `completion` = 1.0 everywhere. It works; do not touch it.
- The four-part no-tool contract *shape*. Only its step-2 hedge clause was wrong.
- The `forbidden_hit: []` record — never quote an escalation literal in a prompt file.

## 9. What I skipped, and why

- **`orchestrator.md`** — never loaded for this task (§0a). Routing prose there is
  unmeasurable.
- **Chasing `ticket` and `tool_calls`** — provably unreachable from prose (§1).
  Inventing prose that *pretends* to reach them (e.g. telling the babylon agent to
  "call query_icinga") would produce a failed tool call, not a score.
- **Pruning for length.** Live footprint went **33,869 → 40,628 chars (+20.0%)**;
  `shared_context.md` 17,918→23,630 and `babylon_agent.md` 15,951→16,998. I chose
  explicitness over brevity because the reader is tier *strong*, not frontier, and the
  failure was a wording failure. **This is the signal to watch:** if cand_0003 lands
  flat at 0.608, the next move is not more prose — it is to *cut* the older,
  now-redundant hedging guidance and leave one rule, then push the §6 escalation.
