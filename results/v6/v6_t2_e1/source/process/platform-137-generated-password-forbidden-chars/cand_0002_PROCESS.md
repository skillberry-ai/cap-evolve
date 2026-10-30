# PROCESS — cand_0002 (iteration 2), parent cand_0001 (val 0.953)

## Headline

**The failure mode moved.** cand_0001 solved `tool_calls` (now 1.0 on 5/5 trials).
The entire remaining loss is `answer`, and it is *not* a missing required fact — all
5/5 required facts are present on all 5 trials. It is the **`wrong-cause` forbidden
clause being hit**, by a *hedged secondary fix option* in the remediation section.
So the fix this iteration is to the **remediation half of the report contract**, not
to evidence gathering.

## How I localised it (ranked issues)

1. Read `score` from all 5 trajectories: `tool_calls=1.0` everywhere, `answer=0.833`
   on exactly 2/5 (t3, t4). `0.7 * 0.833 + 0.3 * 1.0 = 0.883` — matches the reported
   per-trial reward exactly, so `answer` is 100% of the remaining headroom.
2. Resolved each trial's `metadata.trial_dir` and read its
   `verifier/reward-detail.json`. On both failing trials:
   `required_missed: []`, `forbidden_hit: ['wrong-cause']`. On the 3 passing trials,
   `forbidden_hit: []`. **This directly refutes the standing INSIGHTS claim that the
   answer rubric is saturated** — that was true of the seed, not of cand_0001.
3. Regex-scanned the final report text of both failing trials against the 12
   `none_of` strings. Exactly one phrase hits, identically in both:
   **`complexity requirement`**.
4. Read the surrounding sentence. It is the same construction in both trials, inside
   a ranked "Fix options (in order of preference)" list:

   > 2. **Use only letters and digits** — *If password complexity requirements allow:*

   The primary fix (option 1) is correct and fully evidenced. The penalty comes from a
   **conditional caveat attached to a secondary option**, hedging against a
   strength/complexity policy that **no tool result in the conversation ever
   mentioned**. The passing trials differ in exactly one respect: they commit to a
   single fix and never enumerate alternatives with such a caveat. (seed-0 lists two
   options but phrases neither with a policy caveat; seed-2 gives one fix.)

### Ranked issues

| # | Issue | Class | Evidence | Addressed |
|---|---|---|---|---|
| 1 | Remediation section emits a *menu* of ranked fix options; a secondary option carries a conditional caveat invoking an unevidenced cause class, hitting `wrong-cause` | BEHAVIORAL (report contract) | 2/2 failing trials, identical phrasing; 0/3 passing trials | **yes** |
| 2 | Report contract's `Fix suggestions: actionable next steps` is plural and unconstrained — it actively invites the menu | BEHAVIORAL (root instruction) | the rule that produced the misbehavior | **yes** (rewrote it in place) |
| 3 | `tool_calls` evidence gathering | — | already 1.0 on 5/5 | no — solved by cand_0001, left untouched |

## Edits (both in `aap2_agent.md` — the only file this task's report text comes from)

**E1 — rewrote report-contract item 4 in place (BEHAVIORAL).**
`4. Fix suggestions: actionable next steps…` → `4. The fix: ONE recommended change,
at a specific file and line… Not a menu of options`. Per META_INSIGHTS lesson #4 from
cand_0001, I **patched the rule that caused the misbehavior** rather than appending a
competing instruction, so sonnet-4-6 has nothing to arbitrate between.

**E2 — new `#### Recommending the Fix — One Evidenced Change, No Speculative
Alternatives` section (BEHAVIORAL + KNOWLEDGE), 5 numbered rules + a worked example.**
The load-bearing rules:
- **(3)** names the *syntactic shape* of the offending text — `"if the <policy /
  requirement / limit> allows"`, `"assuming <X> is acceptable"`, `"unless <Y> requires
  otherwise"` — and says to **delete** such a caveat, not soften it. This is the rule
  that fires on the exact clause both failing trials wrote.
- **(4)** names the two forbidden *cause classes* abstractly: a provider-side
  transient/outage/availability problem, and a "too small / too short / too weak /
  failed a generic strength or complexity policy" claim. This covers the whole
  `none_of` list by *class*, not by string.
- **(5)** is a **guard against over-correcting**: it explicitly tells the agent that
  explaining intermittency (regenerated per run, random draw, chance) is an *evidenced
  finding* that belongs in the report. Without this, "stop hedging" could suppress the
  `random-per-run` required fact and trade one penalty for another.
- The worked example is a ✅/❌ pair on a fully generic "an API rejected an input with
  a message naming the accepted set" scenario — the reader is sonnet-4-6, and the
  guidance calls for a worked example on tricky contracts.

**E3 — pointer in Critical Rule 2 (salience).** Both failing trials ran 50+ tool calls
before drafting; a rule 460 lines down competes with a long context. Rule 2 is the one
that already says "ALWAYS produce a structured final report", so the constraint on
*what that report may claim* belongs attached to it. It states the prohibition inline
(so it works even if the reader never scrolls to the detail section) and cross-links.

## Verify the fix (did it fire at the exact point of failure?)

- **Point of failure:** drafting the "Fix options (in order of preference)" list in the
  final report — the last assistant turn, after all evidence was in hand.
- **Would E1/E2 have changed it?** Yes, and specifically: E1 removes the plural
  "suggestions/next steps" framing that licensed a ranked list at all; E2 rule 2
  forbids the ranked "fix options" list by name; E2 rule 3 matches the written clause
  *"If password complexity requirements allow"* against a named template and says
  delete it; E2 rule 4 independently forbids the strength/complexity cause class. Four
  independent rules intersect on the one sentence that cost the reward.
- **Could it break the 3 passing trials?** They already do what E1/E2 prescribe
  (commit to one evidenced charset fix, no policy caveat). The edit forbids a behavior
  they don't exhibit and requires nothing they don't already do.
- **Could it break a required fact?** Checked each of the 5 `required` clauses against
  the edit. `random-per-run` was the only one at risk from a "be less speculative"
  rule; E2 rule 5 explicitly protects it, and the worked example's ✅ branch *models*
  the phrasing ("regenerated on every run", "fresh random draw", "chance"). Verified
  by grep that the edited file contains `random`, `regenerated per run`, `chance`.
- **Self-contamination check:** scanned `aap2_agent.md`, `shared_context.md` and
  `orchestrator.md` for all 12 `none_of` strings — **0 hits**. My first draft of the ❌
  example literally contained `complexity requirement`; I rewrote it to "strength
  policy" so a reader that echoes the example's wording cannot trip the clause. This
  was a real near-miss and is worth repeating as a check in any iteration that writes
  prose about a forbidden cause.

## Non-overfitting

Restatement test on every rule: none names a password, a charset, RDS, AWS, a GUID, a
job id, a repo or a role. The rules are stated over "an error message that states the
constraint that was violated", "a value regenerated per run", and two abstract cause
classes (provider-side transience; generic strength/size policy). Any job-failure
report where the log states the violated constraint matches. The worked example uses
`<path>`, `<before>`, `<after>`, "an API", "an input" placeholders only.

## Subagents / parallelism

Did **not** fan out, same reasoning as cand_0001 and now confirmed: cluster count is
1, the loss is a single phrase in a single file section, localised with certainty from
`reward-detail.json` in a few minutes. Parallel edit-agents would conflict on one hunk.
Fan-out is for breadth; there is no breadth here. Diagnosis cost ≈ $0.

## What to preserve

Everything cand_0001 added about deriving the failing file's path from the log and not
treating an empty search as proof of absence — that is what took `tool_calls` to 1.0
on 5/5 and must not be reverted or diluted.

## What I skipped, and why

- **Evidence-gathering / `tool_calls` prose** — already 1.0 on every trial. Pure
  downside risk.
- **Required-fact prose** — `required_missed: []` on all 5 trials. Nothing to gain.
- **`shared_context.md`** — tempting, because "don't name causes your evidence doesn't
  support" sounds domain-general, and `shared_context.md` already has a Grounding
  section. I deliberately kept it in `aap2_agent.md`: the specific thing being fixed is
  the *remediation* half of a **job-failure report**, which only the AAP2 agent emits.
  Putting it in shared context would apply a one-fix-no-alternatives contract to cost,
  Icinga and catalog answers where offering alternatives is often correct — a wide
  blast radius for no measured benefit. If a future iteration sees the same
  hedged-alternative penalty on a *different* domain agent, that is the evidence to
  promote it.
- **`orchestrator.md`** — routing is correct on every trial.

## Escalation (unchanged, still real)

`search_github_repo` returns `total_matches: 0` for repos whose files
`fetch_github_file` serves correctly, and directory fetches error for paths that exist.
Tool-layer defect, out of scope this phase; cand_0001's prose routes around it.

**New, smaller escalation:** the `wrong-cause` clause is substring-matched with
`ignore_case`, so `complexity requirement` is penalised even inside a sentence that
merely *conditions on* that policy in a secondary fix option, rather than asserting it
as the root cause. A prompt cannot reliably teach "avoid this substring in all
framings"; it can only teach "don't raise this cause class at all", which is what I
did. A rubric matching stated *root causes* rather than any occurrence would measure
the intended thing more precisely.
