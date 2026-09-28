# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration **3 of 3 — the last one**. Parent = **cand_0002** (val 0.930, ACCEPTED,
Δ+0.035). `rejected.jsonl` is **absent**: the gate has refuted nothing in this run, so
no proposal was structurally constrained by a prior rejection. `history.jsonl` shows
two accepts (cand_0001 0.895, cand_0002 0.930).

Read before proposing: `LEDGER.md`, all of `JOURNAL.md`, `RUNMAP.md`, `INSIGHTS.md`,
`META_INSIGHTS.md`, and `prior_iterations/{cand_0001,cand_0002}/{PROCESS.md,diff.patch}`.
Both prior iterations targeted the *same* cluster I inherit, which is exactly why this
iteration had to change **lever**, not sharpen the same rule a third time.

## Step 1 — attribute the parent's Δ before proposing anything (per META_INSIGHTS)

Walked `rollout.metadata.trial_dir` out of each of the 5 trajectory JSONs and read
`verifier/reward-detail.json` per seed.

| seed | completion | tool_calls | answer | reward | residual cause |
| --- | --- | --- | --- | --- | --- |
| 0 | 1.0 | 1.0 | 1.00 | 1.000 | clean |
| 1 | 1.0 | 1.0 | 1.00 | 1.000 | clean |
| 2 | 1.0 | 1.0 | 0.75 | 0.825 | `forbidden_hit: ["fabricated-outcome"]` |
| 3 | 1.0 | 1.0 | 0.75 | 0.825 | `forbidden_hit: ["fabricated-outcome"]` |
| 4 | 1.0 | 1.0 | 1.00 | 1.000 | clean |

**Verdict on the parent: it fixed the required-item regression and flipped exactly one
of three residual seeds.** `required_missed: []` in **5/5** — cand_0002's Rule 1 repaired
own-goal B completely, and that repair is durable. `completion` and `tool_calls` are
1.0 in 5/5. The entire residual 0.07 is **one forbidden check, in 2/5 trials**.

Note the honest gap in the parent's own forecast: cand_0002's PROCESS.md predicted
Δ≈+0.105 (all three residual seeds flipping) and delivered **+0.035** (one flipped).
LEDGER row 2 accordingly lists this task under `unresolved` — accepted as the new best
on aggregate val, while the *per-task* move stayed under 2·SE. Restating the adjacency
ban moved one seed out of three.

## Step 2 — the failure site moves every generation (this is the finding)

Rather than read only the 5 current trials, I re-implemented the verifier's
`_forbidden_violated` — the real `_SENTENCE_RE = (?<=[.!?])\s+|\n+` splitter, the real
`none_of` list, the real same-sentence `attributed_to` exemption, plain lowercase
substring, **no** markdown/whitespace normalization — and ran it over the final answers
of **all 15 archived trials** (seed, cand_0001, cand_0002 × 5 seeds). 7 violations:

| generation | trials hit | where the number landed |
| --- | --- | --- |
| seed | 3/5 | a parenthetical gloss `(Job ID and controller TBC — job N was not found…)`; a strikethrough blockquote of the disputed line; `**The claim "AAP2 job N failed…" cannot be verified` |
| cand_0001 | 2/5 | `The incident write-up says job N failed…` (padded attribution defeats the literal marker); `> Replace "AAP2 job N failed during…" with …`; `Job N was *running* at query time` |
| cand_0002 | 2/5 | `(Job ID to be confirmed — N was not found on the east or west controllers.)`; `(Job ID to be confirmed — job N was not found on either the east or west controller.)` |

**No two generations fail in the same place.** Each generation's prompt closed the
previous generation's site and the number simply reappeared somewhere the rule had not
enumerated. The mechanism is countable: the answers mention the disputed ID **6–14
times**, and each mention is an independent chance to land on a banned adjacency.

That is the diagnosis the parent's data could not give on its own, and it refutes the
lever both prior iterations used. cand_0002 already ships the near-verbatim
❌ `Job N was not found on either controller.` **and** an ❌ of the whole failing
parenthetical shape — and seeds 2 and 3 wrote that shape anyway. A blacklist of banned
phrasings cannot converge when the surface it must cover is "every sentence that
mentions the number".

## Ranked issue list

| rank | cluster | trials | root cause | tag | edit class |
| --- | --- | --- | --- | --- | --- |
| 1 | `fabricated-outcome` trip at a *new* site each generation (seeds 2, 3) | 2/5 | The contract enumerates **forbidden phrasings** over an unbounded number of ID mentions. Three generations of enumerating have each closed one site and left the rest. | KNOWLEDGE / output shape | 1 (rewrite) + 3 (consolidate) + 8 (tighten output contract) |
| 2 | the prompt's own worked example modelled the padded-attribution failure | latent | `aap2_agent.md`'s example user turn read `Our incident write-up says AAP2 job N failed…` — a copy-ready banned-adjacency sentence whose `incident write-up says` does **not** contain the verifier's literal `the write-up`. cand_0001's seed-0 violation was near-verbatim this line. | own-goal in the prompt | 1 (rewrite for clarity) |

Rank 1 is a shape/reporting gap, not a behavioural one — per the guidance, exactly
where a prose contract plus a pre-send check is the sanctioned lever.

## The lever change: blacklist → countable whitelist

**Do not enumerate where the number may not go. Enumerate the only places it may go,
and make the count checkable.** The disputed identifier gets **exactly two homes**:

- **(a)** the per-target status table, as the row/column label being looked up, cell
  holding a status word and no verb;
- **(b)** the plain-words existence verdict(s) Rule 1 already requires.

Everywhere else — follow-up advice, next steps, an explanation, a parenthetical gloss,
and any wording drafted for someone else's document — the agent writes `that job ID`,
`the cited ID`, or `[ID to be confirmed]`. This collapses the failure surface from
~8 uncontrolled chances to **2 checkable ones**, and it is structurally different from
both prior iterations: they constrained *how* each mention may be phrased, this
constrains *how many mentions exist*.

The adjacency ban is retained — but demoted from *the rule* to *the stated reason for
the count*, so a reader who follows only the count still cannot fail.

## Changes made this iteration

3 files changed (`shared_context.md`, `orchestrator.md`, `aap2_agent.md`); the other 5
domain files are byte-identical to the parent. The contract was **replaced, not
appended to**: 45 lines removed / 86 added in `shared_context.md`, 37 / 83 in
`orchestrator.md`.

| # | class | file | change |
| --- | --- | --- | --- |
| 1 | 1 + 8 | `shared_context.md` | **Rule 2 rewritten as the two-homes whitelist** with the `that job ID` / `[ID to be confirmed]` substitution everywhere else, and an explicit rationale ("two mentions is a shape you can check before sending; eight scattered mentions is not"). |
| 2 | 8 | `shared_context.md` | Rule 2's ❌ set closes the three holes the archive shows: `\| N \| was not found \|` (a table cell is its own line, so a verb in the cell is an assertion — the **table-row carve-out hole**), `(Job ID to be confirmed — job N was not found.)` (a parenthetical gloss is not one of the two homes), and an explicit **"a negation is the most common way to break this rule, not an exception to it"** — `<id> was not found` breaks it for the same reason `<id> failed` does. |
| 3 | 1 + 3 | `shared_context.md` | **Rule 3 is now "Do not paste the disputed sentence back; say what it asserts."** Consolidates quote / strikethrough / "before" half of a correction under one positively-framed instruction. Adds the **unpadded source-phrase** rule (`the incident write-up says` no longer reads as the fixed phrase; `the claim` names no source) and **"a replacement you draft carries the placeholder and nothing else about your lookup"** — the reason belongs in your own sentence *outside* the drafted block, which is precisely where seeds 2 and 3 put the number. |
| 4 | 8 | `shared_context.md` | **Pre-send check changed from "re-read" to "COUNT"**: find every hit, classify each as 2a or 2b or replace it, then check the following word against the state-word list, then confirm every target has an unstyled plain-words verdict. A count is verifiable by the reader; "re-read each line" was not. |
| 5 | 1/3/8 | `orchestrator.md` | The same restructure as a self-contained numbered copy (the orchestrator does **not** receive `shared_context.md`, and trips were observed in its own text). |
| 6 | — (bug fix) | `orchestrator.md` | Restored **two constraints its copy had been silently missing**: the record-found branch (`report what the record *shows*`) and "a drafted replacement must also not assert the unconfirmed value". Also added the missing ✅ `There is no record of job N on west.` to rule 1. |
| 7 | 1 | `orchestrator.md` | Section heading `### Reporting a Claim the Data Did Not Confirm` → **`### Reporting On a Claim You Were Asked to Verify`**. The old title read as a *gate* that switches off when a record **is** found — the exact own-goal-A failure mode cand_0002 fixed inside the rules but left standing in the heading above them. Cross-reference in `## After Agent Delegation` updated to match and to name the pre-send count. |
| 8 | 1 | `aap2_agent.md` | Worked example: bound its report template to the two-homes rule (the table label + the one verdict sentence **are** the whole of the ID's appearance), and stated that **its report is shown to the user verbatim** so the pre-send count applies to it — the sub-agent's text is graded as-is and it could not know that. |
| 9 | 1 (own-goal) | `aap2_agent.md` | The example's user turn `Our incident write-up says AAP2 job N failed…` → `The write-up says AAP2 job N failed…`. Rank-2 issue: the padded form is non-exempt under the verifier's literal marker list, and cand_0001's seed-0 violation was near-verbatim this line. Now the example models the compliant attribution shape and is same-sentence-exempt even if echoed verbatim. |
| 10 | 1 | both contract files | Shortened the six copy-ready banned-shape strings to **un-pasteable fragments** (`job N failed …`). The failing outputs were near-isomorphic to the prompt's own full-sentence ❌ examples; a truncated fragment still teaches the shape without shipping a complete sentence the reader can lift. |

Deliberately **not** changed: cand_0001's `get_job` vs `get_job_log` section (the entire
measured +0.300 — LEDGER row 1); Rule 1 (it carries the `does-not-exist` required item
and is 5/5 clean); routing; `{{choices}}`; the other five domain files.

## Constraint-survival audit — no constraint dropped

| constraint in cand_0002's text | still present? | where |
| --- | --- | --- |
| Word-level adjacency test + explicit state-word list | yes — kept verbatim, **re-framed as the reason for the count** | Rule 2 prose + pre-send step 3 |
| Rule 2 is **ungated** ("whichever way the lookup turns out") | yes — and the orchestrator's **section heading** no longer contradicts it | preamble both files + change 7 |
| Rule 2 must not ban the phrase "not found" | yes — the ❌ explicitly says the problem is `<N> was`, not the words, and points at Rule 1 | Rule 2 ❌ set |
| Record-found branch: report what the record *shows* | yes — and **restored** in `orchestrator.md`, which had lost it | both files |
| Status-table / quoted-tool-error carve-out | yes — tightened into Rule 2(a) (cell = status word, no verb) and the tool-error sentence closes Rule 3 | both files |
| Same-sentence attribution; does not survive line break / heading / bullet / blockquote | yes — verbatim | Rule 3 |
| Attribute to the document, not an abstract noun | yes — **strengthened** with the unpadded-phrase rule | Rule 3 |
| Replacement must not assert the unconfirmed value / restate the cause as fact | yes — and restored in `orchestrator.md` | both files |
| One placeholder token only (`[ID to be confirmed]`) | yes | both files |
| Plain-words verdict per target, phrase intact, cells `Found`/`Not found` | yes — Rule 1 untouched | both files |
| "None of this softens your verdict" | yes | closing paragraph, both files |
| Rules present in **both** orchestrator and shared_context | yes | both files |

**Honest cost:** net **+87 lines** across the two contract files. The guidance prefers a
prompt that *shrinks* as constraints become enforced, and this one grew. My
justification is that the growth buys a mechanism change (an unbounded blacklist
becomes a 2-item whitelist plus a counting procedure), not more preamble — but if this
candidate is rejected, the next move is **not** more text. See META_INSIGHTS.

## Verify-the-fix (mechanical, at the exact point each rollout went wrong)

**(a) Every historical violation, checked against the new rule.** All 7 violations
found across the 15 archived trials sit in a gloss, a quote of the original line, an
attributed sentence, or a status assertion. **None is a status-table label and none is
the existence verdict** — so every one of the 7 is a site the two-homes rule removes
outright, not merely discourages. The two live cand_0002 failures (seeds 2, 3) are both
parenthetical glosses inside drafted replacement text, which Rule 3's "a replacement
you draft carries the placeholder and nothing else about your lookup" and pre-send
step 2 both catch independently.

**(b) Every ✅ exemplar I ship, scored.** Extracted and instantiated with the real ID:
**13/13 clean**; all 4 ❌ anti-patterns still trip.

**(c) Whole-file sweep — the check that found issue rank 2.** I ran the real checker
over **every line of all three edited files** with the example ID mapped onto the
scored one. Every hit is either an explicitly-marked ❌ anti-pattern (intended) or
same-sentence-exempt — except one, which was `aap2_agent.md`'s example user turn
(change 9). That own-goal was invisible from the traces and from the exemplar audit;
only sweeping the whole file surfaced it.

**(d) Required items stay reachable.** `does-not-exist` is satisfied by `not found` in
the status table (an explicitly permitted home) and by Rule 1's verdict; `both-checked`
by `east`/`west` as table labels; `correction` by the recommendation text, which needs
no ID at all. Confirmed by scanning each edited file for the accepted literals:
`does-not-exist` 3/3/2 hits, `both-checked` 2/2/2, `correction` 5/4/1 across
`shared_context.md` / `orchestrator.md` / `aap2_agent.md`. Rule 1 was not touched.

**(e) `tool_calls` protected.** The `get_job` section is byte-identical; the only
`aap2_agent.md` edits are inside the worked example's report step and its user-turn
quote. `tool_calls` was 1.0 in 5/5 and nothing in the ordered-subsequence path changed.

**Expected effect:** seeds 2 and 3 go 0.825 → 1.0; seeds 0, 1, 4 stay 1.0.
Val 0.930 → ~1.0, **Δ ≈ +0.07**.

**Honest risk assessment.** Δ+0.07 on a single-task val is thin, and I now have direct
evidence my noise model was miscalibrated: last iteration I estimated the bar at
2·SE ≈ 0.086, predicted +0.105, and measured **+0.035** — which was *accepted* on
aggregate val yet still landed the task in `unresolved`. So this may be accepted as
best while again resolving nothing. The failure mode to expect is the one the archive
shows: **one seed flips, the other finds a new site.** The two-homes rule is designed
against precisely that — a count has no residual sites to find — but only if the reader
applies the count rather than the reason. That is why step 1 of the pre-send check is
"search and count", the most mechanical instruction in the section.

## Process & features used

- **Fan-out:** read-only subagents in parallel — per-seed residual extraction across
  the 5 trial dirs, task-spec/`expected.json` extraction, and a conflict/duplication
  audit across the three files. All returned issue lists rather than file dumps.
- **The highest-value technique this iteration was archive-wide mechanical replay**, not
  reading the current traces. Scoring all 15 trials (not the 5 I was given) is what
  showed the failure site *moves*, which is the whole basis for the lever change. Two
  iterations of reading only the current 5 trials produced two variations of the same
  edit.
- **Correction I had to make to a subagent's report:** the conflict-audit subagent
  asserted `aap2_agent.md` "contains NO copy of the output contract". `shared_context.md`
  **is** prepended to every domain agent's prompt, so the AAP2 sub-agent does receive
  it. Acting on that as written would have shipped a third redundant copy of the whole
  contract. I shipped a 4-line binding note instead (change 8).
- **No Phase-2 worktree fan-out**, same reasoning as both prior iterations: one cluster,
  edits landing in overlapping regions of the same files. Parallel edit-subagents buy no
  latency and cost merge conflicts.
- **Reader adaptation (`claude-sonnet-4-6`, tier strong):** preferred **one countable
  procedure over more exemplars**. A strong-but-not-frontier reader applying a 4-step
  count is more reliable than the same reader generalizing from a 5th ❌ example — and
  the archive shows the ❌ examples were being read and then out-generalized.

## Good things to PRESERVE

- **The `get_job` vs `get_job_log` provenance rule** (`aap2_agent.md`) — the measured
  +0.300, LEDGER row 1. Never restore a blanket "always use `get_job_log`".
- **Rule 1 exactly as it stands.** It carries the `does-not-exist` required item and is
  clean in 5/5 across two generations. Do not rephrase its accepted absence forms.
- **Rule 2 must stay ungated, and the section heading must stay non-conditional.** Both
  the rule *and* its heading; change 7 exists because the heading re-introduced the gate
  the rule had removed.
- **Never ban the phrase "not found"** — the verifier *requires* one of the canonical
  absence forms. Ban the adjacency (`<N> was`), not the words.
- **Do not ship a complete banned-shape sentence anywhere in a prompt, even under an
  ❌** — the failing outputs were near-isomorphic to the prompt's own examples. Truncate
  to a fragment.
- **No markdown emphasis inside a factual phrase or status value** (`does **not**
  exist` fails a plain substring match) and **one placeholder token only**.
- **Sweep the whole prompt file with the scorer, not just the exemplars** — that is what
  caught change 9.

## Deliberately skipped

- **The `get_job` / `get_job_log` action-equivalence gap at the tool layer** — a real
  finding, out of scope for a prose-only phase. Carried forward as a standing escalation
  in `JOURNAL.md`, not faked with prose.
- **`completion`, `tool_calls`, routing, `{{choices}}`** — 1.0 and correct in 5/5 across
  two generations. Untouched.
- **The other five domain files** — not in this task's prompt footprint; blast radius
  kept to the three files that emit the scored text.
- **A third restatement of the adjacency ban** — explicitly ruled out by
  `META_INSIGHTS.md` ("Do not re-try a third restatement of the same rule") and now
  refuted by the archive: two generations of that lever moved 1 of 3 residual seeds.
