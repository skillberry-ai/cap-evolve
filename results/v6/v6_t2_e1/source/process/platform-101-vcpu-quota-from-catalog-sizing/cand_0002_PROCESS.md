# PROCESS — cand_0002 (iteration 2; parent = cand_0001, val 0.900)

## Headline

The champion (`cand_0001`) added a rule telling the agent to state the derived
comparison in plain prose. The agent **now obeys that rule** — and still misses
the check, in **5/5 trials, for the same reason every time**. The cause is the
rule's own worked example: it models a sentence shape that does not satisfy the
contract, and its annotation describes a *different* shape than the one it shows.

This iteration does not add a rule. It **repairs the example and sharpens the
rule cand_0001 already introduced**, in the same file and same section.

## Ranked issues

| # | Issue | Trials affected | Action |
|---|---|---|---|
| 1 | `why-over` missed because the derived total is buried inside its own arithmetic ("requests 4 + (3 × 8) + (3 × 16) = 76") | 5/5 | **FIXED** — adjacency rule + repaired example |
| 2 | `why-over` also broken on the limit side by qualifier padding ("exceeds the account's vCPU limit of 64") | 5/5 (same sentence) | **FIXED** — same rule, both sides |
| 3 | Claim rested on a single matchable phrase, so any paraphrase lost it | 5/5 | **FIXED** — three independent anchors |
| 4 | `worker-type-line` citation | **0/5 — now passing** | left untouched (see "what to preserve") |

## How I diagnosed it (order of work)

1. **Pulled per-check `verifier/reward-detail.json` for all 5 champion trials.**
   This is the step that reframed the whole iteration. The miss distribution has
   **completely changed** since iteration 1:

   | check | cand_0001 PROCESS (seed, 10 trials) | **now (champion, 5 trials)** |
   |---|---|---|
   | `worker-type-line` | missed 7/10 | **missed 0/5 — fully fixed** |
   | `why-over` | missed 5/10 | **missed 5/5 — got WORSE** |
   | others | 1/10 each (spiral) | 0/5 — spiral gone |

   So cand_0001's clusters A and C worked outright, and cluster B is now the
   *sole* remaining loss. `answer=0.857143` = 6/7 checks, every trial.

2. **Read the actual answers.** All 5 trials write a genuine prose sentence —
   cand_0001's rule is being followed. The sentence is:

   > "The catalog item requests 4 + (3 × 8) + (3 × 16) = 76 vCPUs in total, which
   > exceeds the account's vCPU limit of 64 for the standard (non-spot) instance
   > bucket by 12 vCPUs."

   Facts, arithmetic, gap: all correct. It still scores a miss.

3. **Ran the real matcher** (`tests/verify.py`, imported in-process) against that
   exact sentence. **All 12 `any_of` forms fail.** Two independent causes:
   - `requests 76` fails — the arithmetic sits between verb and total;
   - `exceeds the 64` fails — "the account's vCPU limit of" pads the limit side.

4. **Tested cand_0001's own worked example, re-instantiated with this task's
   nouns.** It matches **exactly one** form (`exceeds the 120`). The example is a
   single-point-of-failure template: the agent paraphrased the limit side
   slightly, and the one anchor holding the claim up disappeared.

5. **Found the annotation contradicts its own example.** cand_0001's text says
   "Note what that sentence does: `requests 178`, `exceeds the 120`, and the `58`
   gap all appear" — but the example literally reads `requests 2 + 2 x 8 + 5 x 32
   = 178` and `by 58 GB`. Verified mechanically:

   ```
   'requests 178'    in example -> False   (annotation claims True)
   'exceeds the 120' in example -> True
   '58 more'         in example -> False   (annotation claims True)
   ```

   A reader copying the *shape shown* cannot satisfy the rule as *stated*. This is
   the mechanism, and it is a prompt-authoring defect, not a model failure.

## The edit (one file, one section)

`shared_context.md` § *Stating a Derived Comparison in Plain Prose* — the section
cand_0001 created. No new section; no other file touched (all 7 other capability
files are byte-identical to the champion, verified by md5).

1. **Adjacency rule, both sides.** Replaced "put both quantities in the same
   sentence" with: keep every number adjacent to the word introducing it —
   `requests 178` / `exceeds the 120` — and name the two habits that break it
   (arithmetic interposed; limit padded with qualifiers). Both are quoted as
   anti-patterns because both are what the traces actually did.
2. **Three independent anchors.** The claim must state the same fact three
   self-contained ways (total+verb, relation to limit, gap as its own figure), so
   it survives any one being reworded. This directly fixes the single-anchor
   fragility that lost the check.
3. **Repaired the worked example** so its shape matches its annotation:
   bare claim first, arithmetic moved to its own following sentence.
4. **Added a second anti-example** — the inline-arithmetic shape — explicitly
   labelled as the failing one, since that is the exact shape the old example
   taught.

Edit class: **output-contract sharpening** (not new preamble; net change is a
rewrite of 36 lines into 60 within one existing section).

## Verify the fix (counterfactual, against the real scorer)

Not "this reads sensibly" — measured:

- New example shape, re-instantiated for this task → matches **3** forms
  (`requests 76`, `exceeds the 64`, `12 more`) vs the old example's **1**.
- New anti-example → matches **0** (correctly labelled as the failing shape).
- Repaired annotation → all three claimed anchors verified present in its own text.
- **Six plausible paraphrases** a reader might produce from the new rule → all
  **6/6 hit**, 1–3 anchors each, **zero forbidden violations**.
- **End-to-end:** patched each of the 5 real failing answers with *only* this
  sentence-shape change and re-scored with the real `score_answer`:
  **answer 0.857143 → 1.0 on 5/5**, `required_missed: []`, `forbidden_hit: []`.
  Task reward 0.90 → 1.00.

## Non-overfitting audit

- Grepped the edited section for every task-specific token (`76`, `64`, `12`,
  `vCPU`, `lakehouse`, `agnosticv`, `analytics_bu`, `m6i`, job id, GUID,
  `VcpuLimitExceeded`, `rhpds`, `CloudFormation`): **zero hits.** The example uses
  **178/120/58 GB of memory** — a different resource, different numbers.
- The rule restates without any task-specific noun: *"when explaining why one
  quantity exceeded another, put each figure directly after the word that
  introduces it, and state the comparison three independent ways."* Passes the
  restatement test.
- Checked the other 7 files do not model the inline-arithmetic shape anywhere —
  the only occurrence is my own labelled anti-example.

## Why this generalizes

The mechanism is **not** "say 76 vs 64". It is: *a derived comparison loses its
meaning when a figure is separated from the word that introduces it, and a claim
carried by one phrasing is lost to any paraphrase.* Any task asking "why did X
exceed Y" — memory against a cap, cost against a budget, duration against a
timeout — has the same failure surface. Keeping it in `shared_context.md` is
justified here (rather than narrowing to one domain file) because the rule is
about prose construction, and because this is the section that already owns it;
splitting it would leave the broken example live for every other domain.

## Escalations (tool-layer, cannot be fixed by prose)

Both carried forward from cand_0001. Note the **first is now lower-priority**:
`worker-type-line` went 7/10 missed → **0/5 missed**, so the counting procedure
did work and does not need the tool fix as urgently as predicted.

1. `fetch_github_file` returns `content` with no line numbers → an
   `owner/repo:path:line` citation needs hand-counting. A `line_numbers: true`
   option would make the miss class structurally impossible. *Status: mitigated
   by prose, confirmed working.*
2. `lookup_catalog_item` returns `found: false` with an **empty** `similar_items`
   even for near-matches of the real directory name — the original trigger for
   the search spiral. *Status: mitigated by cand_0001's stop rule; the spiral did
   not recur in 5/5 trials.*
3. **New, and the real structural finding:** the `why-over` contract is a finite
   `any_of` substring list with `fold_markup` **off**, so a factually perfect,
   well-written answer fails on punctuation and word order. I am fixing it by
   teaching the agent a shape robust *across* the list, but the honest note is
   that this check rewards phrasing over correctness. Recorded in
   `FRAMEWORK_IMPROVEMENTS.md`.

## What to preserve (do NOT revert)

- cand_0001's **counted-listing procedure** for line citations — measurably took
  `worker-type-line` from 7/10 missed to 0/5. All 5 trials write the numbered
  listing and cite line 19 correctly.
- cand_0001's **two-miss stop rule** in `aap2_agent.md` — the 15-call spiral did
  not recur; tool_calls=1.0 in 5/5.
- The **no-bold / bare-digits** rule — still load-bearing (a bold-wrapped bare
  claim still misses; verified against the matcher).

## Process notes

- **Did not fan out subagents**, same deliberate call as iteration 1 and for the
  same reason: one task, 5 trials, and all 5 fail on one identical sentence. The
  diagnosis is a single aggregation plus one scorer import; parallel agents would
  have re-derived the same table five times. The fan-out guidance is calibrated
  for many tasks across many clusters — the split shape here does not match it.
- **The transferable lesson:** when a prior iteration's rule is being *obeyed*
  and the check still fails, suspect the rule's **example**, not the model.
  Testing cand_0001's own example against the real matcher — and finding it
  matched 1 form while its annotation claimed 3 — is what located this. Worth
  making a standing step: *every worked example you ship should be run through
  the real scorer, and its annotation checked against its own text.*

## What I skipped

- Rewording the line-counting procedure — it is working (0/5 missed). Iteration
  1's handover said to stop if that check was still missing; the inverse applies,
  so I left it alone.
- The INSIGHTS.md suggestion to relocate the rules from `shared_context.md` into
  `aap2_agent.md`. That was contingent on cand_0001 being **rejected** (dilution
  hypothesis); it was accepted, and the measured cause of the remaining loss is a
  broken example, not dilution. Moving files would not have fixed it.
- Any edit to the other 7 capability files — no trace evidence implicates them,
  and widening the diff would only add regression risk to a one-check deficit.
