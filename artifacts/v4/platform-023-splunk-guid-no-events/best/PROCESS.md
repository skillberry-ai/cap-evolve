# PROCESS — what I did this iteration (explainability; REQUIRED)

Iteration 2 of 3. Parent: **`seed`** (val 0.960 — cand_0001 was rejected, champion
unchanged). One task, 5 trials. Weights are `tool_calls 0.2` / `answer 0.8`;
`answer = (required_hits + forbidden_clean) / 4` (3 required facts + 1 forbidden
group), so **each required fact and the forbidden group are each worth 0.2 of
reward.** `tool_calls` was 1.0 on all 10 trials measured so far (seed + cand_0001):
there is no tool-side headroom on this task, and all headroom is answer prose.

## The single most important input: WHY cand_0001 lost 0.16

cand_0001 is not just "not enough" — it made the task measurably worse, and I could
only build on it by finding the mechanism. Per-trial rewards, read from each trial's
`verifier/reward-detail.json` + `agent/agent.jsonl` via `rollout.metadata.trial_dir`:

| | t0 | t1 | t2 | t3 | t4 | mean |
| --- | --- | --- | --- | --- | --- | --- |
| seed | 1.0 | **0.8** | 1.0 | 1.0 | 1.0 | 0.96 |
| cand_0001 | **0.8** | **0.8** | **0.6** | **0.8** | 1.0 | 0.80 |

The forbidden-hit rate went from **1/5 → 4/5**, and every single hit in all ten
trials is the same bigram: `never started`. Nothing else on the forbidden list ever
appeared. Locating each hit relative to the sub-agent/orchestrator boundary (the
graded answer is the two concatenated):

| trial | hit text (abridged) | half |
| --- | --- | --- |
| seed t1 | "This could be because: (1) the pod **never started** and therefore never emitted logs, (2) …" | orchestrator |
| cand_0001 t0 | "does **not** mean the provision succeeded, **never started**, or ran without errors" | sub-agent |
| cand_0001 t0 | "It does **not** let us conclude the provision \"**never started**\" or \"never ran\"" | orchestrator |
| cand_0001 t1 | "…the pod **never started** so there were no container logs to ship" | sub-agent |
| cand_0001 t2 | "**Does NOT establish:** That the provision succeeded, that it **never started**, …" | sub-agent |
| cand_0001 t3 | check table cell: distinguishes "pod ran silently" from "pod **never started**" | orchestrator |

**Two mechanisms, both caused by cand_0001's own text:**

1. **It printed the banned strings in the prompt.** Its `Do NOT write | Write
   instead` table and prose contained `"never started"`, `"never ran"`,
   `"was never provisioned"`, `"we cannot conclude it never started"` and
   `"it may never have been provisioned"` — 8+ literal occurrences. The matcher is
   case-insensitive substring with **no negation awareness**, so every one of those
   strings is a loaded gun. Telling this reader "do not claim X" makes it write
   "this does not establish X" — reproducing X verbatim. 3 of the 5 hits above are
   exactly that shape.
2. **It kept — and mandated — the structure the phrase lives in.** Its part 2 was
   "state the bounded positive, then state the limit", and it explicitly said
   "Unresolved possibilities still belong in the answer". So the answer still
   contained a list of hypotheses; only the framing changed. t3 shows the subtlest
   version: the hypothesis migrated into the *next-checks table*, as the thing a
   check would "distinguish" between.

So the refuted lever is not "an empty-result contract" in general — it is **a
contract that names the phrases and still asks for an enumeration of explanations.**

Secondary, independent finding from cand_0001 t2 (the 0.6): it also missed the
`no-events` required fact. It wrote "Zero error-level log entries were returned" /
"No error-level log entries exist". Fusing the qualifier into the absence
("no **error-level log** entries") destroys every plain form of the negative — the
bare absence was never stated anywhere in 3.7 KB of report. This is a real
communication defect, not only a matcher artifact.

## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | An empty search is reported as a **list of candidate explanations** (seed: "This could be because (1)…(3)"; cand_0001: "Does NOT establish that…", and a check described by the hypotheses it would distinguish). One of those candidates is always "it did not run", which is on the forbidden list. 6/6 observed hits live in this structure. | 1 (10/10 trials emit the structure; 5/10 trials landed on the banned string) | Nothing tells the agent what an absence licenses, and `orchestrator.md:21` / `shared_context.md:10` order it unconditionally to "answer with the cause". Naming the banned phrases (cand_0001) makes it worse, not better. | BEHAVIORAL (overconfident) | Replace the structure: a fixed output shape whose only forward-looking slot is **checks**, plus a rule banning hypothesis enumeration in any form, plus a vocabulary rule — and **zero banned strings in the prompt text** |
| 2 | The absence is stated only in qualified form, so the plain negative never appears | 1 (1/10 trials; cost 0.2) | No rule says to state the bare result before its scope | BEHAVIORAL (format) | "State the absence bare, then qualify it", modelled in the shape |
| 3 | `shared_context.md:141` `**Infer retired from absence**` — a named, generalizable license to read state off missing data, in the same file as the new rule | 0 measured | Over-broad heading on a rule that is actually about one complete query | KNOWLEDGE | Keep the behaviour, add the reason, fence the generalization |
| — | Routing, tool choice, tool args, completion | 0 | `tool_calls=1.0` on 10/10 trials, `gate=1.0`, completion not in weights | — | **no change** (deliberately untouched) |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | tighten the output contract + worked example | `orchestrator.md` new `### When a Search Comes Back Empty` (placed inside `## Response Style`, before `### Source Citations`) | A 4-part answer shape whose last part is a **check list in "change → data returned" form**. There is no slot for a hypothesis. Generalizes because it is written against "a search that returned zero rows", with `<identifier>`/`<window>`/`<index>` placeholders | Yes — gated on an empty result; no trajectory with data reaches it |
| 1 | resolve a rule conflict | same section | States that answering "what does this let us conclude" is the orchestrator's job and **not** a re-synthesis — the `## After Agent Delegation` "NEVER re-synthesize" rule otherwise competes with the new shape. Resolves rather than stacks | Yes — all 10 trials already answered it; this only settles which rule governs |
| 1 | add a rule with its reason | same section, rule 2 "List checks, not explanations" | Names all four disguises the hypothesis actually took in the traces: a list of possible causes, a "does NOT establish" list, scare quotes, and *the thing a check would distinguish between*. A generic "don't assert a cause" rule misses the last two — t3 proves it | Yes — additive, empty-result-gated |
| 1 | add a rule with its reason | same section, rule 3 "Vocabulary" | Bans the word *never* and the verbs *confirms* / *proves* / *shows* in an empty-result answer. A word-level ban cannot be satisfied by a hedge, which is how cand_0001's phrase-level ban was evaded | Yes — these words assert more than an absence carries, in any domain |
| 1 | narrow an over-broad rule | `orchestrator.md:20-25`, `shared_context.md:9-14` | "answer with the cause" now applies *when a tool result shows the cause*; "not established yet, here is the check" is named as a complete answer. Removes the pressure instead of adding a rule that fights it | Yes — unchanged whenever a result does show the cause, i.e. every other trajectory shape |
| 1 | same contract for the sub-agent half | `shared_context.md` new `## When a Search Comes Back Empty` | 3 of the 6 hits were in the sub-agent half, and `shared_context.md` is the only file read by *whichever* domain agent runs (I still cannot tell from the artifacts whether babylon or aap2 handles this Splunk call). Domain-general by construction — it covers CloudTrail, cost, monitoring and DB emptiness too | Yes — empty-result-gated |
| 2 | add a missing format rule | rule 1 in both files + the shape's `**Result: no events — 0 results.**` line | Bare absence as its own statement, scope in the next sentence | Yes — strictly more information than before |
| 3 | add the reason, fence the generalization | `shared_context.md` `**Missing from active results means retired**` | Behaviour preserved verbatim (treat as retired, do NOT re-run the query); now says *why* (that query returns the complete active set) and that a log/event/cost search is not complete in that way | Yes — identical verdict on the same input |
| 1 | domain knowledge, most-specific file | `babylon_agent.md` `### Using Splunk Logs`, `aap2_agent.md` `**Investigation flow with Splunk:**` step 5 | What a zero-event Splunk result is bounded by (index, matched namespace, window, severity) and the concrete pivot order off Splunk — `errors_only`, widen, `list_anarchy_subjects`/tower job refs, provisions DB, `query_aap2` job events. These name the domain's real next sources, which is what keeps the `next-step` fact robust | Yes — additive to sections that had no empty-result rule |
| 1 | remove counter-pressure | `aap2_agent.md` `**Root Cause & Recommendations:**` | Fields 1–3 are mandatory and push toward inventing a cause. They now accept "not established — <what you searched> returned no events", with the check under Fix suggestions | Yes — fields still required; only the permitted *value* set widens, and only when searches were empty |

**Nothing in any prompt file contains a forbidden substring** (verified by grep over
all 8 files for all 8 `none_of` entries: no match). **No instance values** (grep for
`hq7wz`, `2026-06-19`, `2026-06-21`, `platform-023`: no match in any prompt file).

## Verify-the-fix (against the exact point each trial went wrong)

- **seed t1, orchestrator, "This could be because: (1) the pod never started…"** —
  the new shape replaces that table outright: its only forward-looking slot is
  "Next checks — each named by the change to make and the data it would return",
  and rule 2 forbids a "list of possible causes" by name. Rule 3 forbids the word
  *never*. There is no position in the prescribed answer where that clause fits.
- **cand_0001 t0/t2, sub-agent, "does not mean … never started" / "Does NOT
  establish: … that it never started"** — this shape was *produced by cand_0001's
  instruction*. It is gone: the limit is now a single fixed sentence in `whether`
  form ("whether the operation ran, whether it succeeded, or why it failed"), and
  rule 2 names the "does NOT establish" list as forbidden. The prompt no longer
  supplies the string to negate.
- **cand_0001 t3, orchestrator, check cell 'distinguishes "pod ran silently" from
  "pod never started"'** — rule 2's last clause is exactly this case ("not as the
  thing a check would distinguish between"), and the shape's own first check row is
  the same check written the right way: `drop the error/severity filter and re-run →
  whether any lines at all exist for <identifier>`. This is the site a
  cause-assertion rule alone would have missed.
- **cand_0001 t1, sub-agent, "…the pod never started so there were no container logs
  to ship"** — appeared inside a parenthetical list of possibilities. Rule 2 removes
  the list; rule 3 removes the word.
- **cand_0001 t2's missing `no-events`** — rule 1 plus the shape's
  `**Result: no events — 0 results.**` line make the bare negative explicit, with the
  "error-level / index / window" qualifiers moved to the following sentence.
- **The three required facts are now hardwired by the shape rather than left to
  luck** — checked against `expected.json`'s `any_of` lists: `no events` and
  `0 results` (→ `no-events`); `does not tell us` in the shape and `does not mean` in
  the self-check line (→ `cannot-conclude`); `widen the time window` plus the domain
  files' `errors_only` / `query_aap2` / `list_anarchy_subjects` / AnarchySubject
  (→ `next-step`). Seed got 3/3 in 5/5 trials by luck; cand_0001 shows luck runs out.
  So I expect variance down as well as the mean up.
- **The self-check line is the closest thing to code enforcement available in this
  phase** ("is the bare absence in it, is the limit stated in words, is a named next
  check in it, is every sentence about the data") — a re-read pass, because for this
  reader tier a checkable list beats another paragraph of principle.

## Process & features used

- **Serial, by deliberate choice.** The run-level guidance asks for one diagnosis
  subagent per trajectory-group and one edit subagent per issue in its own worktree.
  This project's train/val/test are the *same single task* with *one* failure
  cluster, and the whole diff is 125 changed lines across 4 files (`orchestrator.md`
  49, `shared_context.md` 58, `aap2_agent.md` 12, `babylon_agent.md` 6, the other
  four files 0 — measured against `project/seed_capability/`); parallel edit
  branches would have bought merge risk and no additional coverage. I spent the effort on evidence
  breadth instead: all 10 trials' `reward-detail.json` + `agent.jsonl`, each hit
  located by character offset relative to the sub-agent/orchestrator boundary, plus
  `expected.json`, `instruction.md` and `task.toml`. cand_0001's own PROCESS.md
  already carried the 8-file prompt audit, so re-running that subagent would have
  re-bought a known result.
- **Prior iterations read:** `RUNMAP.md`, `LEDGER.md`, `rejected.jsonl`,
  `JOURNAL.md`, `INSIGHTS.md`, `META_INSIGHTS.md`, and
  `./prior_iterations/cand_0001/{PROCESS.md,diff.patch}` in full. What I took from
  them: (a) the orchestrator half must be edited, `shared_context.md` alone cannot
  reach it — kept; (b) the placement hypothesis in META_INSIGHTS ("if val is flat,
  treat it as placement") is **not** what happened — val was not flat, it fell, and
  the mechanism is content, so I did not spend the iteration on placement; (c) the
  INSIGHTS caution about negation-blind matching turned out to be the whole story,
  and cand_0001's own diff violated it 8 times.

## Good things to PRESERVE (do not let a future iteration undo these)

- **No prompt file may contain any string on the `forbidden.none_of` list.** This is
  the measured cause of cand_0001's -0.16: 8 literal occurrences → 4/5 hit rate.
  A future iteration that adds a helpful-looking "do not say X" table re-breaks this.
  Grep before shipping.
- **Rule 2 ("List checks, not explanations") and specifically its last clause**, the
  hypothesis-as-what-a-check-distinguishes case. It looks redundant; cand_0001 t3 is
  the proof it is not.
- **The vocabulary rule must stay word-level** (*never*, *confirms*, *proves*,
  *shows*), not phrase-level. A phrase-level ban is satisfiable by a hedge, which is
  how the seed's 4 passing trials escaped by accident.
- **The block must exist in `orchestrator.md` itself.** `shared_context.md` is not
  prepended to the orchestrator prompt, and 3 of 6 hits were in the orchestrator
  half. Consolidating the duplicate into `shared_context.md` to save tokens silently
  reopens half the failure.
- **The conditional on "answer with the cause"** in both files.
- Do **not** touch routing, tool selection, or `errors_only`/window arguments:
  `tool_calls=1.0` on 10/10 trials.

## Deliberately skipped (cluster + why)

- **`cost_agent.md`, `icinga_agent.md`, `ocpv_agent.md`, `security_agent.md`** — all
  four are untouched this iteration (cand_0001 edited the last two). Neither runs for
  this task, so those edits were unmeasurable, and this iteration's whole thesis is
  that *what the prompt says* moved the number by 0.16 in the wrong direction — so I
  kept the diff to the four files that are actually read for this task and can be
  attributed. `icinga_agent.md:190-195` (forces a root cause) and `cost_agent.md`
  (no epistemic scaffolding at all) still carry the same latent defect; they are a
  real finding for a run whose split includes a cost or monitoring task.
- **`aap2_agent.md:299-301`** ("'Pod failed to start' is never an acceptable root
  cause") — conditioned on *a log showing a pod failing to start*, so it cannot fire
  on an empty search. Left alone.
- **Shrinking the risk surface by having the orchestrator not restate the epistemic
  analysis** — considered and rejected on evidence: 3 of the 6 hits were in the
  sub-agent half, so suppressing the orchestrator half would not have saved t1/t2,
  and it would trade against the `{{choices}}` mandate.

## Escalation (needs code, cannot be fixed with prose)

Unchanged from cand_0001 and now demonstrated rather than predicted: the
`inferred-from-silence` check is negation-blind substring matching, so a *correct*
sentence ("this does not establish that it never started") scores as a violation —
that is literally how cand_0001 lost 0.16 while writing more careful reports than the
seed. The prose fix available in this phase is to steer the answer away from restating
hypotheses at all, which is independently good report-writing. But the grader should
be negation-aware (or should score the claim, not the substring); that belongs in
`tests/verify.py`, not in prompt text.
