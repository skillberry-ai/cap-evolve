# PROCESS — cand_0006

## Headline

The champion is **not** stuck at a one-item ceiling, and iterations 3–5 measured
**nothing**. Both of those are factual findings from this iteration, and both
change what the right edit is.

Two facts I established before editing:

1. **cand_0003, cand_0004 and cand_0005 are byte-identical to the seed.** Every
   `.md` file matches (`diff -q` across all 8, all three candidates) and all three
   share one `cap_hash` — `ce387d4f…`, which is also the seed's. Their val scores
   of 0.808 / 0.616 / 0.680 are **pure trial noise on the unmodified champion**,
   not the effect of an edit. Their PROCESS.md files are the unfilled template and
   JOURNAL carries `optimizer_context_warning` for each: those three optimizers ran
   out of context before writing anything. The LEDGER's Δ of −0.032 / −0.224 /
   −0.160 therefore measures the *task's own variance*, not three bad ideas.
2. **That variance is large: the same prompt scores 0.52–1.00 across trials.**
   Pooling every trial of the unmodified seed bundle (25 in this run's job dir plus
   20 in the reused `v6_g2_e1` dir) gives rewards of 1.00, 0.84, 0.68 and 0.52. So
   cand_0001's headline claim — "this task is NOT flaky, all 10 trials are exactly
   0.84, stderr 0.0" — was an artifact of a 10-trial window, and the framework's
   `stderr 3.7e-17` is false precision. The task is genuinely flaky, which is what
   the brief said in the first place.

## Ranked issue list

Re-clustered from the per-rubric-item read-across of all 45 trials of this task
(`reward-detail.json` per trial, grouped by prompt bundle via file hash + mtime).

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **A — a figure sourced from a *second* query is reported as if it came from the first** | cost-402 | The agent re-queries with the preset that *does* collect the missing roll-up, gets real numbers (`total_estimated_cost_usd` 56391.84, `overall_utilization_pct` 60.95), puts them on the slide, and never says the first query's `0.0` was never a measurement. Having the number retires the disclosure in the agent's mind. This is the champion's dominant failure: 4/4 of its 0.84 trials and 11/11 of its 0.68–0.52 trials. | BEHAVIORAL | CONTRACT + worked example in `cost_agent.md`; domain-general provenance rule in `shared_context.md` |
| 2 | **B — the inability sentence is carried by markup, not by prose** | cost-402 | cand_0002 wrote the remedy as ``the **`utilization` preset**``. The contract does not set `fold_markup`, so `_contains` is a raw substring test and the backtick between `utilization` and `preset` blocks the rubric form `utilization preset`. 5/5 of its trials missed on exactly this. | KNOWLEDGE (of the reader's own output habits) | explicit "plain text, not inside backticks" instruction |
| 3 | **C — one of the two required sentences is dropped, whichever one the edit did not emphasise** | cost-402 | Seed drops *zeros-not-measured*; cand_0001 drops *share-not-from-this-call*; cand_0002 drops it again. The two never co-occur under any bundle tried so far. They are separate rubric items and compete for the same closing paragraph. | CONTRACT | two separately-mandated, separately-checked sentences |
| 4 | **D — the explicit request is overridden by the file's default workflow** | cost-402 | `cost_agent.md`'s "ODCR waste report workflow" opens "1. Call `utilization` (grouped by account-id)". The user named `unused_cost` grouped by instance family; several trials wandered through `utilization(account-id)`, `utilization(instance-type)` and `inventory`, burning calls and in 2 trials losing the required counts entirely (the 0.0 / gate-failure trial in the reused dir). | BEHAVIORAL | scope the workflow to open-ended requests only |

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| A, C | CONTRACT + worked example | `cost_agent.md` — new "Reporting contract when a requested figure needs a key this preset left unfilled" | Mandates **two separate active-voice sentences**, says each must be checked separately, and adds the clause the champion's failure needs: *"If you go on to run that second preset and it returns the missing roll-up, you still owe both sentences above."* Generalizes to any tool with a fixed result shape whose modes fill different subsets of it. | Yes — adds obligations, removes none; cannot reduce `tool_calls` (unordered-subset, no forbidden calls) |
| A, B | KNOWLEDGE | `cost_agent.md` — same section | A per-preset table of which `totals` keys each preset populates vs returns as unfilled `0.0`, plus a *tell* for distinguishing an unfilled zero from a real one (inconsistency with neighbouring rows). Plus the plain-text-not-backticks instruction. | Yes — pure addition |
| C | CONTRACT | `cost_agent.md` — worked example | Models the shape **inability → why the zero is not a measurement → where the real figure lives**, with the inability as the paragraph's first words and the preset name unbackticked. The reader imitates the example more reliably than it obeys prose. | Yes |
| D | BEHAVIORAL | `cost_agent.md` — workflow preamble | "When the user names the preset, grouping, or window, use exactly what they named as your first call"; the workflow is scoped to requests that name none. Discriminating condition, not a blanket override. | Yes — the workflow still fires for every open-ended request, which is every case it was written for |
| A, C | BEHAVIORAL, domain-general | `shared_context.md` — extends *Grounding* | Three rules, none naming a cost noun: (i) a zero/empty field in a fixed result shape is an unfilled slot — and is *not* evidence of an outage or cache lag either; (ii) explaining an absence does not discharge the request for the figure, each needs its own active-voice sentence; (iii) if a follow-up query supplies what the first lacked, say which query each figure came from. | Yes — narrowing conditions inside an existing rule |

## Verify-the-fix

I rebuilt the scenario's real verifier offline (`tests/verify.py`, stdlib-only) with
the golden tool call and the real seeded tool result, then **validated the harness
against ground truth**: it reproduces all five observed (reward, missed-item)
combinations exactly — 0.84/`share-not-from-this-call`, 0.84/`zeros-not-measured`,
0.68/both, 0.52/both, 1.00/none. Only then did I use it to measure edits.

- **Cluster A, the champion's exact failure point.** I took the champion's real
  answer verbatim — the one that reports $56,391.84 and 60.95% from the follow-up
  query — and appended **only** the provenance paragraph my edit now mandates.
  `0.84 → 1.000`, `required_missed` empty. Nothing else about the answer changed,
  so the disclosure sentence is the whole delta at the point it went wrong.
- **Clusters A+C, the shape itself.** 48 answers written by following the worked
  example's shape — 4 independent paraphrases of the zeros sentence × 4 of the
  share sentence × 3 tails (refuse / **second query succeeded and is reported** /
  second query empty) — **all 48 score 1.000.** The "fetched" tail is the champion's
  failure mode and it passes in all 16 of its combinations.
- **Negative controls still fail, so the measurement discriminates.** Champion
  as-is `0.84` (missing `zeros-not-measured`); cand_0001's real answer `0.84`
  (missing `share-not-from-this-call`); cand_0002's real answer `0.84` (missing it
  too, via the backtick). My edits are the difference between these and the 48.
- **Cluster B confirmed mechanically.** Lower-casing cand_0002's answer and testing
  each of the 20 `any_of` forms directly: zero hits, while `utilisation preset`
  appears in the text with a backtick between the words. Removing the backtick
  alone takes that same answer to 1.000.
- **Forbidden guard re-checked.** An answer using my worked example's wording —
  including the quoted `"0% utilisation"` — scores `forbidden_hit: []`, because the
  sentence ends "would be wrong", an `attributed_to` phrase. No regression risk there.
- **Rubric-form check on my own wording.** I verified which phrasings actually land
  a form: "never requests" and "only ever requests" match **nothing** in
  `zeros-not-measured`'s list. This is why the edit tells the reader to say *does
  not measure* / *never measured* / *placeholder* rather than "never requests" —
  cand_0001's rationale language, which the rubric does not accept.
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
  full, RUNMAP, LEDGER, the whole JOURNAL, INSIGHTS, META_INSIGHTS, rejected.jsonl.
  cand_0003–0005 have template-only PROCESS.md and no diff — I established by file
  hash that they contain no edit, which is why their Δ values must not be treated
  as evidence about any approach.
- **What I took from cand_0001/0002 and kept:** the preset/`totals` knowledge table
  and the two-separate-sentences contract are theirs and are preserved in
  substance. cand_0002's two mechanical findings — active voice beats passive, and
  backticks block raw substring forms — are both carried forward explicitly.
- **What I did NOT re-try, on their evidence:** framing the zeros as a data gap,
  cache lag or backend outage (6/10 seed trials did this and all 6 missed; I added
  an explicit guard against it instead); telling the agent to re-query to *recover*
  the zeros as if they were lost data; shrinking the knowledge table for salience
  (cand_0002 showed the content was not the problem).
- **One prior claim I had to correct, because the edit depends on it:** cand_0001
  recorded that the follow-up `utilization` call "returns empty by design (no row is
  seeded)". It does not. In 11 of the 15 trials in this run's job dir it returns
  `total_estimated_cost_usd` 56391.84 and `overall_utilization_pct` 60.95 for
  `group_by=instance-family`; it returns empty only for `account-id` and
  `instance-type`. That is precisely why cluster A exists — the agent gets real
  numbers and then under-attributes them — and an edit built on "the follow-up is
  empty" would have aimed at the wrong behavior.

## Good things to PRESERVE

- The per-preset `totals` table (which keys are populated vs unfilled). Confirmed by
  cand_0001's RESULT to flip `zeros-not-measured` 10/10-missed → 5/5-hit.
- Two **separate** active-voice sentences, one per unproducible figure, each checked
  separately. The two rubric items have never co-occurred under any bundle that
  mandated only one combined passage.
- The "plain text, not inside backticks" instruction for the remedy sentence. This
  contract does not set `fold_markup`; cand_0002 lost 0.16 to a single backtick.
- The **"you still owe both sentences even if the follow-up query succeeds"** clause.
  This is the only edit in the run that addresses the champion's actual dominant
  failure, and it is verified to be the whole delta on the champion's own answer.
- The offline verifier harness, and the habit of validating it against ground truth
  before trusting it.

## Deliberately skipped

- **Routing.** `task.toml` has `services=["cost"]`; `orchestrator.md` routes money /
  capacity-reservation questions to `investigate_costs`. Correct in 45/45 trials.
  No edit.
- **`tool_calls` and `completion`.** 1.0 in 44/45 trials under every bundle; the one
  gate failure is in the reused dir and is a wandering-calls artifact that cluster D
  addresses indirectly. Not worth a targeted edit.
- **The other five domain agent files.** Not in this task's prompt footprint.
- **Chasing the 0.52 trials as a distinct cluster.** They are the same two missed
  required items plus noise in the counts, not a separate mechanism.

## Escalation (no prose edit can fix this)

**The gate cannot resolve an effect of this size on this task at n=5.** The
unmodified champion's own trials span 0.52–1.00. Three successive no-op candidates
were scored −0.032, −0.224 and −0.160 and recorded in the LEDGER as if they were
edits; a real +0.16 fix is well inside that spread. The `stderr 3.7e-17` the
framework reports comes from a 10-trial window in which every trial happened to
land on 0.84 and is false precision. This is a measurement-budget problem, not a
prompt problem: the honest remedy is more trials per evaluation (or paired/common-
random-number scoring across candidates), and it is recorded in
FRAMEWORK_IMPROVEMENTS.md. I have made the edit as large and as verified as I can —
48/48 shape-conformant answers at 1.000 with three discriminating negative controls
— but whether it clears the bar at n=5 is partly a coin flip, and a rejection should
**not** be read as evidence against the mechanism.

---

# DIAGNOSIS.json

Written alongside this file.
