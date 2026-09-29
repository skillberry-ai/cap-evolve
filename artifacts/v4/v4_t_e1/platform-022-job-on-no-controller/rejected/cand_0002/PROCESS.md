# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 2 of 3. Parent = **cand_0001** (val 0.895, ACCEPTED, Δ+0.300).
`rejected.jsonl` does not exist yet — nothing is refuted, so no proposal was
structurally constrained by a prior rejection.

I read `LEDGER.md`, the whole `JOURNAL.md`, `RUNMAP.md`,
`prior_iterations/cand_0001/{PROCESS.md,diff.patch}`, `INSIGHTS.md` and
`META_INSIGHTS.md` before proposing. cand_0001 targeted the *same* two clusters I
inherit, so this iteration is a **sharpening of its edit, not a new one**.

## Step 1 — attribute the parent's Δ before proposing anything

cand_0001's `META_INSIGHTS.md` told me to branch on which metric moved. So I walked
`rollout.metadata.trial_dir` out of each of the 5 trajectory JSONs and read
`verifier/reward-detail.json` + `agent/agent.jsonl` per seed. (Trap: each seed dir
holds **two** timestamped trials — the seed/baseline run and cand_0001's. A naive
`find … | head -1` returns the baseline and makes cand_0001 look like it failed.
Walk the exact `trial_dir` from the trajectory JSON.)

| seed | tool_calls | answer | reward | residual cause |
| --- | --- | --- | --- | --- |
| 0 | **1.0** | 0.75 | 0.825 | `fabricated-outcome` forbidden trip |
| 1 | **1.0** | 1.0 | 1.000 | clean — **but only by luck** (see below) |
| 2 | **1.0** | 1.0 | 1.000 | clean |
| 3 | **1.0** | 0.75 | 0.825 | required **`does-not-exist` MISSED** |
| 4 | **1.0** | 0.75 | 0.825 | `fabricated-outcome` forbidden trip |

**Verdict on the parent: cluster 1 worked perfectly, cluster 2 did nothing.**
`tool_calls` went 0.0 → 1.0 in 5/5 — that is the *entire* +0.300. `answer` mean is
**0.85 before and 0.85 after**: cand_0001's Rules 1–3 moved it by zero. This is
exactly the branch its own META_INSIGHTS predicted ("phrasing rules read but not
applied"), but the real reason turned out to be more specific and more damning than
"not applied" — see Step 3.

Also new this iteration: `required_missed` is **no longer empty**. cand_0001's
PROCESS.md says "`required_missed: []` in 5/5, do not touch required content". That
was true of the seed and is **false of cand_0001** — seed 3 now misses
`does-not-exist`. cand_0001's own edit caused a new required miss. That PRESERVE note
is superseded (recorded below).

## Step 2 — the environment is broken, and it is why cluster 2 looks unfixable

Reading the raw tool results rather than the summaries: `get_job` on the disputed id
does **not** 404. On east the mock **synthesizes a full job record and inserts it into
the store** (`status: running`, `failed: false`, a plausible template/guid/duration),
and the subsequent west call then returns
`{"error": "Duplicate key in store 'jobs': id '<N>' already exists"}`.

The task's own `golden.json` expects `HTTP 404` from **both** controllers, and
`seeds/platform.json` contains no such job id. So the fixture and the running
simulation disagree. This is a tool-layer defect, escalated in JOURNAL.md — **not**
something prose can fix. But it is the *precondition* for the residual failures, and
recognising it is what made the prose fix designable at all.

## Step 3 — the real root cause: cand_0001's Rule 2 scored two own-goals

Both residual clusters trace to the *same* rule the parent added.

**Own-goal A — the trigger never fires.** Rule 2 read: *"Once a lookup shows the
entity does not exist, do not write …"*. Because the mock returned a record, that
precondition was **false**, so the agent correctly judged the rule inapplicable — and
then wrote `Job <N> was *running* at query time.` (seed 4). That sentence is a
*truthful* report of what the tool returned, and it trips `fabricated-outcome`
anyway. A rule gated on "the entity does not exist" cannot fire in the one
environment state that actually occurs.

**Own-goal B — the ✅ exemplars steer away from the required wording.** The verifier
accepts `does not exist` / `no such job` / `not found` / `does not appear` /
`cannot be found` / `is not present` / `no record`. cand_0001's ✅ exemplars were
`No job with ID <N> exists on either controller.` and `Neither controller has a record
of job ID <N>.` — **neither contains any accepted form** ("record of" ≠ "no record").
And its ❌ exemplar banned `Job <N> was not found on either controller.`, which
*does* contain the accepted form "not found". So the rule pushed the agent off the
required phrasing and explicitly forbade a phrase that would have satisfied it. Seed
3 duly wrote `does **not** exist as a valid record` and `❌ No` — and missed.

**Own-goal B has a second edge: markdown emphasis.** `required` matching is a plain
case-insensitive substring over the whole answer, so `does **not** exist` does not
match `does not exist`. Mechanically confirmed:

```
HIT   'Job N does not exist on west.'      -> ['does-not-exist', 'both-checked']
MISS  'Job N does **not** exist on west.'  -> ['both-checked']          <- seed 3
HIT   '| west | Not found |'               -> ['does-not-exist', 'both-checked']
MISS  '| west | ❌ No |'                   -> ['both-checked']          <- seed 3's table
```

**And seed 1 passed by luck.** Its text is `job <N> **failed**` — the bold broke the
forbidden literal. Strip the emphasis and seed 1 scores 0.75. One of the two "clean"
trials is one formatting whim away from failing, so the fix has to make the shape
deliberate rather than accidental.

## Ranked issue list

| rank | cluster | trials | root cause | tag | edit class |
| --- | --- | --- | --- | --- | --- |
| 1 | `identifier-adjacent-to-outcome-word` (seeds 0, 4 — and seed 1 latent) | 3/5 | Rule 2's trigger is gated on non-existence, which never holds here; and it says nothing about the verbatim **quote** of the disputed line, only about the drafted replacement | KNOWLEDGE / output shape | 1 (rewrite for clarity) + 3 (consolidate) |
| 2 | `absence-verdict-not-in-plain-words` (seed 3) | 1/5 | No rule requires a per-target existence verdict at all, and Rule 2's exemplars actively steered off the canonical wording; nothing forbids emphasis inside a factual phrase | KNOWLEDGE / output contract | 8 (tighten the output contract) |

Both are *shape/reporting* gaps, not behavioural ones, which per the guidance is
precisely where a prose contract + pre-send check is the sanctioned lever (a prose
self-check would **not** have been legitimate for a behavioural gap).

## Changes made this iteration

Every change **sharpens cand_0001's existing sections in place** — "resolve conflicts,
don't stack rules". Rules stayed at three; one constraint was added, none dropped.

| # | cluster | class | file | change |
| --- | --- | --- | --- | --- |
| 1 | 2 | 8 | `shared_context.md` | **New Rule 1 — plain-words existence verdict per target.** `not found` / `does not exist` / `no record of …` / `found`; keep the phrase intact (`does not exist`, never `does **not** exist`); status cells labelled `Found`/`Not found`, never `Yes`/`No`. |
| 2 | 1 | 1 | `shared_context.md` | **Rule 2 rewritten as a mechanical adjacency test.** The identifier must not be the word directly before `failed, ran, was, were, completed, succeeded, crashed, caused, took`. Trigger widened to the whole answer **"whichever way the lookup turns out"** — kills own-goal A. Its ❌ for `was not found` now explains the problem is `<N> was`, **not** the words "not found", and points at Rule 1's wording — kills own-goal B. |
| 3 | 1 | 3 | `shared_context.md` | **Rules 1+3 consolidated into a single Rule 3** covering restatement, *the verbatim quote*, and the drafted replacement alike — "a quoted line is not exempt". cand_0001 masked the id only in the replacement, which is why seed 0 tripped on a bare verbatim quote of the disputed line. |
| 4 | both | 8 | `shared_context.md` | **Pre-send line-by-line check** at the end of the section — the lever cand_0001's JOURNAL and INSIGHTS both nominated as "next if `answer` doesn't move". |
| 5 | both | 4 | `shared_context.md` | `## Tool Result Handling` → **"An error payload is not a record."** A 404 / "not found" / internal store-or-index error for one object means that target is `not found`; quote the error; never read an error as evidence the object exists. This is the rule the two answer=1.0 seeds followed implicitly. |
| 6 | both | 1/3/8 | `orchestrator.md` | The same three rewritten rules + pre-send check, self-contained (the orchestrator does not read `shared_context.md`, and trips were observed in its output). |
| 7 | both | — (conflict resolution) | `orchestrator.md` | `## After Agent Delegation` forbade the orchestrator from restating sub-agent findings *at all* — which makes "state a verdict for every target" **unsatisfiable after delegation**. Added item 4: a verdict the user asked for (claim adjudication, go/no-go, corrected wording) is the answer the evidence was gathered *for*, not a re-summary. Narrow discriminating condition, not a loosening. |
| 8 | 2 | 1 | `orchestrator.md` | `## Report Generation` was the only place in any file licensing "**bold** for emphasis", unqualified. Now: emphasis on a whole label or clause, never inside a factual phrase or status value. |
| 9 | both | 1 | `aap2_agent.md` | The worked example's own step 3 said *"Report that no job with that ID exists"* — wording that satisfies **none** of the accepted absence forms. Replaced with a modelled per-controller table + plain-words verdict, and extended the counterfactual branch: report what a record *shows* rather than confirming the claim, and an error about the store still means `Not found`. |

Deliberately **not** changed: the `{{choices}}` contract; cand_0001's `get_job` vs
`get_job_log` section and its three de-conflicted mandates (that edit is the entire
measured +0.300 — LEDGER row 1); routing.

## Constraint-survival audit

| constraint in cand_0001's text | still present? | where |
| --- | --- | --- |
| Attribution must be in the same sentence as echoed words | yes | Rule 3, opening sentence |
| Attribution does not survive line break / heading / bullet / blockquote | yes | Rule 3, verbatim |
| Attribute to the document, not to an abstract noun ("the claim") | yes | Rule 3 prose + ❌ exemplar retained |
| Never put an unconfirmed identifier next to an outcome verb | yes — **strengthened** into a word-level adjacency test with an explicit word list | Rule 2 |
| State absence as an existence finding, not as something the entity did | yes | Rule 2's `shows status` vs `was running` contrast |
| Replacement text must not carry the unconfirmed value | yes | Rule 3, now also covering the quote |
| Do not restate the cause as established fact | yes | Rule 3, closing clause |
| "Constrains prose, not labels" carve-out (status table + quoted tool error) | yes — **explicitly preserved**, cand_0001's PRESERVE note honoured | after Rule 3 in both files |
| `[ID to be confirmed]` is the placeholder token (not `TBD`/`TBC`) | yes — single token, unchanged, both files | Rule 3 |
| "None of this softens your verdict" | yes | closing paragraph, both files |
| Rules present in **both** orchestrator and shared_context | yes — cand_0001's PRESERVE note honoured | both files |

Net: **no constraint dropped; two added** (plain-words verdict, no emphasis inside a
phrase). The `shared_context.md` section grew ~17 lines; `orchestrator.md`'s grew
~20. Growth is confined to the one genuinely new constraint plus the mechanical word
list — the rest is rewriting, not appending.

### One PRESERVE note from cand_0001 is now superseded

> *"Do not touch the required-answer content — `required_missed` was empty in 5/5."*

True of the seed, **false of cand_0001**: seed 3 misses `does-not-exist` because
cand_0001's own exemplars steered off the canonical wording. Change 1 deliberately
touches required-answer *wording* for that reason. Everything else in cand_0001's
PRESERVE list is honoured.

## Verify-the-fix (mechanical, not plausible-sounding)

I re-implemented the verifier's required + forbidden checks against the real
`expected.json` and the real splitter `(?<=[.!?])\s+|\n+`, then extracted **every ✅
exemplar I actually shipped** out of the three edited files and scored them with the
placeholder id retargeted to the scored one, so the *shape* is what gets tested:

```
--- 13 shipped ✅ exemplars, id retargeted ---           all clean
--- shipped ❌ exemplars must still trip ---
  TRIPS (good)  Job N was running at query time.              <- seed 4's exact shape
  TRIPS (good)  Job N was not found on either controller.
  TRIPS (good)  The claim "job N failed during the provision" cannot be verified.
  TRIPS (good)  A safer sentence: "An AAP2 job failed ... (Job ID TBC — job N was not found.)"
```

Then the five real failing shapes, rewritten exactly as the shipped rules direct:

```
CLEAN  seed 0 trip 1  ('The incident write-up says job N failed ...')
CLEAN  seed 0 trip 2  (bare verbatim quote of the disputed line)
CLEAN  seed 3 miss    ('does **not** exist as a valid record')
CLEAN  seed 4 trip    ('Job N was *running* at query time')
CLEAN  seed 1 luck    ('job N **failed**', previously saved only by the bold)
```

And a full rule-compliant answer for **this environment** (east returns a fabricated
record, west returns the store error) scores:

```
answer=1.000  reward=1.000
   OK  req:does-not-exist    OK  req:both-checked
   OK  req:correction        OK  forb:fabricated-outcome
```

Two details worth stating plainly, because they are what makes this a fix rather than
good advice:

- The adjacency rule is **marker-independent**. I verified 7 rewrites that satisfy it
  *without* using any word from the verifier's `attributed_to` list, and none trip. So
  the rule does not depend on the agent happening to pick a blessed attribution
  phrase — which is how seed 0 failed (it wrote "the **incident** write-up", and
  inserting a word between "the" and "write-up" defeats the literal marker).
- Seed 0's trip 1 is a reminder that the marker list is matched literally. Rule 3's
  exemplars therefore model the exact document phrasings, and Rule 2 gives an escape
  that needs no marker at all.

**Expected effect:** seeds 0, 3, 4 go 0.825 → 1.0; seeds 1, 2 stay 1.0; seed 1 stops
depending on luck. Val 0.895 → ~1.0, **Δ ≈ +0.105**.

**Honest risk assessment.** My estimate of the gate's bar is 2·SE ≈ 0.086 on this
measurement. Δ+0.105 clears it, but **only if all three residual trials are fixed** —
fix two of three and the move is ≈+0.07 and gets rejected as noise. That is why every
rule here is mechanical (a word-adjacency test and a literal phrase list) rather than
a principle the reader has to apply judgment to. It is also why I did not spend the
iteration on anything else: there is no second, independent source of gain left.

## Process & features used

- **Fan-out:** 3 read-only subagents in parallel — (a) per-seed residual extraction
  from the 5 trial dirs, (b) the guidance docs' binding constraints, (c) a
  conflict/duplication audit across the three files. All returned issue lists rather
  than file dumps, keeping the large artifacts out of the main context.
- **Fan-out finding that changed the edit:** the audit found the
  `| east | ❌ Not found |` cell already prescribed the *right words* in both files —
  so Rule 1 only needed to ban `Yes`/`No` and emphasis, a much smaller edit than I
  had planned. It also found the `## After Agent Delegation` conflict (change 7),
  which I would have shipped as an unsatisfiable rule otherwise.
- **No Phase-2 worktree fan-out**, same reasoning as cand_0001: two clusters whose
  edits land in overlapping regions of the same three files. Parallel edit-subagents
  buy no latency and cost merge conflicts. Deliberate, not a fallback.
- **`Skill(diagnose)` could not be invoked** (returned "Execute skill: diagnose"); I
  read `guidance/diagnose/SKILL.md` directly instead. Logged in
  `FRAMEWORK_IMPROVEMENTS.md`.
- **Reader adaptation:** the guidance says a strong reader wants the *smallest* set of
  exemplars, while the INSTRUCTIONS' reader note asks for worked examples. I resolved
  it toward **mechanism over volume**: one word-level adjacency test with an explicit
  word list, and I cut one ✅ exemplar from Rule 3 that duplicated the shape another
  already pinned. A word list is cheaper for this reader to apply than three more
  examples to generalize from.

## Good things to PRESERVE

- **Everything on cand_0001's PRESERVE list except the `required_missed` note** —
  above all: never restore a blanket "always use `get_job_log`" (that is the measured
  +0.300), keep the rules in **both** files, keep the prose-not-labels carve-out.
- **Rule 2 must stay ungated.** Its "whichever way the lookup turns out" clause is
  load-bearing: re-adding a "once the lookup shows it does not exist" precondition
  re-creates own-goal A, and in this environment the precondition is never true.
- **Rule 2 must not ban the phrase "not found".** The verifier *requires* one of the
  canonical absence forms, and "not found" is one. Ban the adjacency (`<N> was`), not
  the words.
- **No markdown emphasis inside a factual phrase or status value.** `does **not**
  exist` fails a plain substring match; this cost a whole required item.
- **One placeholder token only** (`[ID to be confirmed]`). A second spelling gives the
  reader a menu.

## Deliberately skipped

- **The tool-layer defect** (`get_job` fabricating a record and poisoning the store) —
  out of scope for a prose-only phase; escalated in JOURNAL.md, not faked with prose.
- **`completion` / routing / `{{choices}}`** — 1.0 and correct in 5/5.
- **cand_0001's `get_job` section** — it is the accepted +0.300. Untouched except that
  its worked example's step 3 wording now models the canonical absence phrasing.
- **`babylon_agent.md` and the other four domain files** — not in this task's prompt
  footprint; blast radius kept to the three files that emit the scored text.
