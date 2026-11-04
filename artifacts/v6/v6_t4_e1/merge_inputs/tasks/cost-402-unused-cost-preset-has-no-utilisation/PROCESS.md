# PROCESS — cand_0006

## Headline

The champion is **not** stuck at a one-item ceiling, and iterations 3–5 measured
**nothing**. Both of those are factual findings from this iteration, and both
change what the right edit is.

Two facts I established before editing:

1. **cand_0003, cand_0004 and cand_0005 are byte-identical to the seed.** Every
   `.md` file matches (`diff -q` across all 8, all three candidates) and all three
   not the effect of an edit. Their PROCESS.md files are the unfilled template and
   JOURNAL carries `optimizer_context_warning` for each: those three optimizers ran
   `stderr 3.7e-17` is false precision. The task is genuinely flaky, which is what
   the brief said in the first place.

## Ranked issue list


| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 3 | **C — one of the two required sentences is dropped, whichever one the edit did not emphasise** | cost-402 | Seed drops *zeros-not-measured*; cand_0001 drops *share-not-from-this-call*; cand_0002 drops it again. The two never co-occur under any bundle tried so far. They are separate rubric items and compete for the same closing paragraph. | CONTRACT | two separately-mandated, separately-checked sentences |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A, C | CONTRACT + worked example | `cost_agent.md` — new "Reporting contract when a requested figure needs a key this preset left unfilled" | Mandates **two separate active-voice sentences**, says each must be checked separately, and adds the clause the champion's failure needs: *"If you go on to run that second preset and it returns the missing roll-up, you still owe both sentences above."* Generalizes to any tool with a fixed result shape whose modes fill different subsets of it. | Yes — adds obligations, removes none; cannot reduce `tool_calls` (unordered-subset, no forbidden calls) |
| C | CONTRACT | `cost_agent.md` — worked example | Models the shape **inability → why the zero is not a measurement → where the real figure lives**, with the inability as the paragraph's first words and the preset name unbackticked. The reader imitates the example more reliably than it obeys prose. | Yes |
| D | BEHAVIORAL | `cost_agent.md` — workflow preamble | "When the user names the preset, grouping, or window, use exactly what they named as your first call"; the workflow is scoped to requests that name none. Discriminating condition, not a blanket override. | Yes — the workflow still fires for every open-ended request, which is every case it was written for |
| A, C | BEHAVIORAL, domain-general | `shared_context.md` — extends *Grounding* | Three rules, none naming a cost noun: (i) a zero/empty field in a fixed result shape is an unfilled slot — and is *not* evidence of an outage or cache lag either; (ii) explaining an absence does not discharge the request for the figure, each needs its own active-voice sentence; (iii) if a follow-up query supplies what the first lacked, say which query each figure came from. | Yes — narrowing conditions inside an existing rule |

## Verify-the-fix

I rebuilt the scenario's real verifier offline (`tests/verify.py`, stdlib-only) with

- **Cluster A, the champion's exact failure point.** I took the champion's real
  query — and appended **only** the provenance paragraph my edit now mandates.
- **Clusters A+C, the shape itself.** 48 answers written by following the worked
  example's shape — 4 independent paraphrases of the zeros sentence × 4 of the
  share sentence × 3 tails (refuse / **second query succeeded and is reported** /
  failure mode and it passes in all 16 of its combinations.
- **Negative controls still fail, so the measurement discriminates.** Champion
  too, via the backtick). My edits are the difference between these and the 48.
- **Cluster B confirmed mechanically.** Lower-casing cand_0002's answer and testing
  each of the 20 `any_of` forms directly: zero hits, while `utilisation preset`
  appears in the text with a backtick between the words. Removing the backtick
- **Forbidden guard re-checked.** An answer using my worked example's wording —
  sentence ends "would be wrong", an `attributed_to` phrase. No regression risk there.
- **Rubric-form check on my own wording.** I verified which phrasings actually land
  a form: "never requests" and "only ever requests" match **nothing** in
  `zeros-not-measured`'s list. This is why the edit tells the reader to say *does
  not measure* / *never measured* / *placeholder* rather than "never requests" —
- **Non-overfitting.** Grepped both edited files for every literal in this task
  (`2847`, `1212`, `56391`, `60.95`, `p4d`, `instance-family`, `720`, the window
  date, the result ids). The only hits are pre-existing seed lines in the GPU-abuse
  indicator list, untouched by me. Every rule restates without a cost-specific
  noun: "a tool returns a fixed result shape and fills only the fields its query
  mode collects."

## Process & features used

- **Serial, deliberately** — not the fan-out the brief pushes for. The decisive
  evidence was a *read-across* of per-rubric-item detail between prompt bundles
  (which bundle misses which item), plus a file-hash comparison proving three
  candidates were unmodified. One subagent per trajectory-group would have handed
  each agent one side of a comparison and none of them would have seen either
  finding. cand_0001 and cand_0002 reached the same conclusion for different
  reasons; with a single-task split I treat it as settled and recorded it in
  META_INSIGHTS.
- **Prior iterations read:** cand_0001 and cand_0002 PROCESS.md + diff.patch in
  cand_0003–0005 have template-only PROCESS.md and no diff — I established by file
  as evidence about any approach.
- **What I took from cand_0001/0002 and kept:** the preset/`totals` knowledge table
  and the two-separate-sentences contract are theirs and are preserved in
  substance. cand_0002's two mechanical findings — active voice beats passive, and
  backticks block raw substring forms — are both carried forward explicitly.
- **What I did NOT re-try, on their evidence:** framing the zeros as a data gap,
  an explicit guard against it instead); telling the agent to re-query to *recover*
  the zeros as if they were lost data; shrinking the knowledge table for salience
  (cand_0002 showed the content was not the problem).
- **One prior claim I had to correct, because the edit depends on it:** cand_0001
  recorded that the follow-up `utilization` call "returns empty by design (no row is
  `total_estimated_cost_usd` 56391.84 and `overall_utilization_pct` 60.95 for
  `group_by=instance-family`; it returns empty only for `account-id` and
  `instance-type`. That is precisely why cluster A exists — the agent gets real
  numbers and then under-attributes them — and an edit built on "the follow-up is
  empty" would have aimed at the wrong behavior.

## Good things to PRESERVE

- The per-preset `totals` table (which keys are populated vs unfilled). Confirmed by
- Two **separate** active-voice sentences, one per unproducible figure, each checked
  separately. The two rubric items have never co-occurred under any bundle that
  mandated only one combined passage.
- The "plain text, not inside backticks" instruction for the remedy sentence. This
- The **"you still owe both sentences even if the follow-up query succeeds"** clause.
  This is the only edit in the run that addresses the champion's actual dominant
  before trusting it.

## Deliberately skipped

- **Routing.** `task.toml` has `services=["cost"]`; `orchestrator.md` routes money /
  No edit.
  gate failure is in the reused dir and is a wandering-calls artifact that cluster D
  addresses indirectly. Not worth a targeted edit.
- **The other five domain agent files.** Not in this task's prompt footprint.
  required items plus noise in the counts, not a separate mechanism.

## Escalation (no prose edit can fix this)

**The gate cannot resolve an effect of this size on this task at n=5.** The
random-number scoring across candidates), and it is recorded in
FRAMEWORK_IMPROVEMENTS.md. I have made the edit as large and as verified as I can —
**not** be read as evidence against the mechanism.

---

# DIAGNOSIS.json

Written alongside this file.
