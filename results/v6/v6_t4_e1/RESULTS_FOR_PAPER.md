 # v6 core results for the paper: Tables 1–4 (Seed, T-opt, T-mrg, Global)

Prepared 2026-10-22 for the agent that edits the MLSys 2027 PARSEC paper. This file is
self-contained: every number needed for the four main tables and their prose is here, with its
definition and source. The v6 T-mrg experiment is now complete, so the paper's green
`\missingresult{...}` placeholders can be replaced.

**Conventions to keep (from the paper's `handoff.md`):** use train / validation / test; name the
arms Seed, T-opt, T-mrg and Global; introduce them as Task-wise (T) and Global (G); put new
wording in blue (`\new{}` / `newcontent`); do not use internal run names (v6_t2, v6_t4, m1/m2/m3)
in manuscript prose. Names for the three merge methods are suggested in §1.

---

## 0. What changed, in one paragraph

The paper currently treats integration as the open risk: T-opt fits every selected training task,
but its 34 private bundles cannot be deployed together. T-mrg now answers that question.
**Merging the 34 independently optimized English edits into one bundle, without looking at any
score, produced a bundle that scores the same as Global on the sealed test split.** Merge by order:
test +0.046 over Seed; smart merge: +0.041; Global: +0.037. The task-by-task differences from Global
(+0.009 ± 0.014 and +0.004 ± 0.012) are within noise. The T path reached this at about half of
Global's total cost (Table 2), but its merged bundles are 1.3–2.4× larger than Global's (Table 3).
This reverses the hypothesis, taken from the historical v4 pilot, that task-local English edits
would not compose. The reframing is therefore no longer "does integration work?". It becomes "it
works; here is what integration costs and what it changes."

---

## 1. T-mrg protocol (needed for Methods §3.2 and Experimental Setup §4.3)

This also answers the open author comment in §3.2 about whether T-mrg uses validation.

- **Inputs:** the 34 T-opt champions, each as a diff against the Seed (188 hunks over 7 of the 8
  files; `ocpv_agent.md` is untouched by every task). About half the hunks overlap a hunk from
  another task. The hotspots are `shared_context.md` (24 tasks touch it) and `aap2_agent.md` (15).
- **Blind rule:** no merge method saw any train, validation or test score while merging. Each
  merged bundle was built, frozen, and only then evaluated. This keeps T separate from Global: a
  merge that read scores would be optimizing the shared bundle against an aggregate objective,
  which is what Global does. The only score-derived input is the one inherent to T: each edit was
  chosen by its own task's optimization. In addition, merge by order uses the per-task gains T-opt
  had already recorded, and only to fix the order in advance.
- **Three methods, all reported:**

  | Suggested paper name | Rule | Judgment? | Build cost |
  |---|---|---|---|
  | **Merge by order** | Apply the 34 diffs one after another with `git merge -X theirs` semantics, so a later diff wins any region it contests. Order: ascending T-opt gain (champion − Seed); ties broken by task name; the highest-gain edit is applied last. | none (script) | 10 s, no LLM |
  | **Smart merge** | A fresh Claude Code agent (Claude Opus 5.5) plus three sub-agents it spawned merged the 34 edits by meaning: dedupe overlapping rules, reconcile conflicts, keep each task's intent. It read only the Seed, the 34 diffs, each task's request, and each task's optimizer rationale with every score, reward and trial count removed. Every decision is logged. | yes, without scores | 49.6 min; 10.15M tokens; ≈ $14.16 |
  | **Non-conflicting hunks** | Keep every hunk that no other task's hunk overlaps (91 of 188); drop every contested hunk. Hunk-level, not task-level: a task-level rule would keep only 2 of the 34 edits. | none (script) | 10 s, no LLM |

- **Evaluation:** each frozen bundle was scored on the **train split (67 tasks)** and the **sealed
  test split (66 tasks)**, with **5 trials per task**. The 5 trials are 3 at seeds 0–2 plus a
  2-trial top-up at fresh seeds 3–4, added to confirm the surprising 3-trial result. **The
  validation split was not used by T-mrg.** Comparisons are paired by task against the Seed's
  existing measurement from the Global run, which was not re-measured.
- **Infrastructure:** one cluster job per task on its own node, at most 30 concurrent. Trials that
  failed for infrastructure reasons were rerun or left out, never scored as zero (same rule as the
  other arms). Seven smart-merge tasks lost to gateway disconnects were re-run cleanly.

Suggested wording for the §3.2 comment: *T-mrg builds each merged bundle without seeing any score,
freezes it, and evaluates it once on the train and test splits. It does not use the validation
split; no merge method is selected on a held-out split, and all three methods are reported.*

---

## 2. Table 1 — Reward on train, validation and test (main result)

Mean reward per split. Δ is the change from the Seed, paired by task; ± is the standard error of
the per-task paired difference. The 95% CIs are task-level bootstrap intervals (10,000 resamples).

| Arm | Train (67) | Validation (67) | Test, sealed (66) |
|---|---|---|---|
| Seed | 0.830 (10 trials/task) | 0.821 (4) | 0.813 (10) |
| **Task-wise (T)** | | | |
| T-opt — 34 private bundles + Seed for the rest; not deployable | 0.937, Δ +0.107 ± 0.017 (5) | not measured | not measured |
| T-mrg · merge by order | 0.902, Δ +0.072 ± 0.018 (5) | not used | **0.858, Δ +0.046 ± 0.015 (5); CI [+0.016, +0.074]** |
| T-mrg · smart merge | 0.908, Δ +0.078 ± 0.021 (5) | not used | **0.854, Δ +0.041 ± 0.016 (5); CI [+0.011, +0.072]** |
| T-mrg · non-conflicting hunks | 0.880, Δ +0.050 ± 0.015 (5) | not used | 0.828, Δ +0.015 ± 0.018 (5); CI [−0.020, +0.049] |
| **Global (G)** | | | |
| Global (`cand_0005`) | 0.884, Δ +0.053 ± 0.017 (4) | 0.814, Δ −0.005 ± 0.016 (3, gate trials) | **0.850, Δ +0.037 ± 0.013 (10); CI [+0.011, +0.065]** |

**Head-to-head on test, paired by task:** merge by order − Global = +0.009 ± 0.014; smart merge −
Global = +0.004 ± 0.012; non-conflicting − Global = −0.022 ± 0.015; merge by order − smart merge =
+0.004 ± 0.014. On train: merge by order − Global = +0.019 ± 0.011; smart merge − Global = +0.024 ±
0.015.

**Comments the table needs (caption or text):**
1. **The rows answer different questions.** T-opt's train number combines 34 mutually exclusive
   bundles; it is a fit diagnostic, not a deployable artifact. Every T-mrg and Global row is one
   deployable bundle. Both T-mrg and Global were optimized using train tasks, so their train
   column is fit for both. Test is the held-out comparison.
2. **Test result:** merge by order and smart merge are statistically indistinguishable from Global.
   Non-conflicting hunks is the weakest: its test gain is not distinguishable from zero. So the
   value lies in the edits several tasks wanted to make, mostly shared rules.
3. **Global's validation figure** comes from the trials of the validation-gate run that accepted
   `cand_0005` (195 trials, about 3 per task). It is paired against a 4-trial Seed remeasurement
   on validation. **Do not use −0.018 (0.804 vs 0.821) here:** that figure measured `cand_0002`,
   the previous accepted candidate, not the final bundle (`paper_notes.md` already records this).
   Either way, Global's validation gain is not distinguishable from zero while its test gain is
   positive.
4. **Trial counts differ:** 5 per task for T-mrg, 10 for Global on test. The SEs are similar
   because per-task variation dominates.
5. **3 → 5 trials (robustness check, for text or the supplement):**

   | | Train, 3 trials | Train, 5 trials | Test, 3 trials | Test, 5 trials |
   |---|--:|--:|--:|--:|
   | Merge by order | +0.085 ± 0.019 | +0.072 ± 0.018 | +0.059 ± 0.016 | +0.046 ± 0.015 |
   | Smart merge | +0.086 ± 0.022 | +0.078 ± 0.021 | +0.040 ± 0.019 | +0.041 ± 0.016 |
   | Non-conflicting | +0.050 ± 0.016 | +0.050 ± 0.015 | +0.011 ± 0.020 | +0.015 ± 0.018 |

   The two extra trials lowered merge by order by 0.013 and left the other two essentially
   unchanged. The ranking and the "equal to Global on test" conclusion did not change.

---

## 3. Table 2 — Cost, tokens and compute time

T-mrg rows are **cumulative**: T-opt + its merge + its own 5-trial evaluation on train and test.
They therefore read directly against Global. The figure in brackets is the increment over T-opt.
The Seed row holds the three shared Seed measurements (train 10, validation 4, test 10 trials per
task). It is common to all arms and is not charged to any of them.

| Arm | Eval $ | Optim. $ | **Total $** | Eval tokens | Optim. tokens | **Total tokens** | Eval h | Optim. h | **Total h** |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Seed (shared reference) | 215.29 | — | **215.29** | 65.0M | — | **65.0M** | 74.1 | — | **74.1** |
| T-opt | 38.26 | 281.09 | **319.35** | 11.3M | 283.4M | **294.7M** | 24.9 | 19.4 | **44.3** |
| T-mrg · merge by order | 186.73 (+148.47) | 281.09 (+0) | **467.82** | 57.8M (+46.5M) | 283.4M (+0) | **341.2M** | 43.7 (+18.7) | 19.4 (+10 s) | **63.0** |
| T-mrg · smart merge | 239.18 (+200.93) | 295.25 (+14.16) | **534.43** | 75.0M (+63.7M) | 293.6M (+10.2M) | **368.6M** | 43.8 (+18.9) | 20.2 (+0.8) | **64.0** |
| T-mrg · non-conflicting | 159.08 (+120.82) | 281.09 (+0) | **440.17** | 48.8M (+37.5M) | 283.4M (+0) | **332.3M** | 44.2 (+19.3) | 19.4 (+10 s) | **63.6** |
| Global (`cand_0005`) | 594.08 | 355.02 | **949.10** | 184.3M | 155.0M | **339.3M** | 220.9 | 8.9 | **229.8** |

**Definitions:**
- **Eval** is the target agent running tasks. **Optim.** is the optimizer agent proposing edits,
  plus, for the smart merge, the LLM merger. The other two merges are 10-second scripts with no
  LLM.
- **Dollars and tokens** are as recorded by the runs. The one exception is the smart merge's
  $14.16, an estimate: its measured tokens priced at Claude Opus 5.5 list price ($4 input, $20
  output, $0.20 cache read, $5 cache write per million tokens). 63% of that is output tokens.
- **Compute time** is each trial's own agent run time (from its recorded start and end), summed,
  plus each optimizer call's duration, summed. Work ran in parallel on up to 15–30 cluster workers,
  so this measures effort, not wall clock. Global's run took 66.1 h of wall clock. The T-mrg
  evaluation of all three bundles took well under a day; the final 2-trial top-up of all three took
  1.5 h.
- **Global's evaluation breakdown:** validation gates (candidate and incumbent) $294.22; train
  incumbent sweeps $94.31; train screens $14.34; sealed test $138.02; post-run validation
  remeasurement of `cand_0002` $53.20. Total $594.08.

**Comments the table needs:**
1. **Dollars:** the two merges that match Global on test cost $468 and $534 in total, against
   Global's $949. That is 49% and 56% of Global.
2. **Cost to produce a deployable bundle before opening test:** T about $319–334 (T-opt + merge;
   T-mrg's own evaluation is the test-and-train measurement that follows). Global $811 (optimizer
   + train screens and sweeps + validation gates and remeasurement). Neither includes the shared
   Seed.
3. **Tokens:** totals are similar (332–369M for T-mrg, 339M for Global), but the mix is reversed.
   T spends 77–85% of its tokens in the optimizer; Global spends 54% in evaluation.
4. **Compute time:** Global used about 3.6× the compute hours of T-mrg, almost all in evaluation.
   T-opt's optimizer time (19.4 h) exceeds Global's (8.9 h) because it ran 34 separate searches.
5. **Test evaluation costs differ by design:** Global's test line ($138) used 10 trials per task,
   T-mrg's 5, so like-for-like Global's test line would be about half.
6. **Not a controlled efficiency claim:** the arms used different gates, budgets and trial counts.
   Keep the paper's existing caveat.

**This changes numbers already in the paper:**
- The paper reports Global at **$1,164.39**. That equals Seed **$215.29** + Global **$949.10**.
  Table 2 separates them because the Seed measurements serve every arm. Paper text that says
  "Global cost $1,164" should either say so explicitly or use $949 alongside the Seed row.
- The paper's split of Global's evaluation ($83.09 Seed sweep, $494.06 screens + gates, $232.21
  test) mixes Seed and candidate measurements. The figures above separate them: Global's test was
  $138.02 and the Seed's test was $94.19.
- The paper's **38.0 h (T-opt)** and **51.5 h (Global)** used the runs' `runner_seconds`, the wall
  time of each evaluation batch while its trials ran in parallel. That undercounts compute, and by
  different amounts for T and G. Table 2 uses one definition for every arm: summed per-trial agent
  time plus optimizer time. That gives **44.3 h (T-opt)** and **229.8 h (Global)**. The paper's
  cost table and the "summed compute time" sentences need updating to match.
- T-opt's dollar figures are unchanged ($281.09 optimizer + $38.26 eval = $319.35; the paper's
  $281.12 + $38.25 = $319.37 differs only by rounding across 34 runs).

---

## 4. Table 3 — Skill edits in words

Word-level diff of each arm's eight skill files against the Seed (14,753 words), summed over files.

| Arm | Added | Removed | Net | Files changed | Resulting words | vs Seed | vs Global |
|---|--:|--:|--:|--:|--:|--:|--:|
| Seed | — | — | — | — | 14,753 | — | 0.59× |
| T-opt (34 champions, summed) | +47,288 | −460 | +46,828 | 7 of 8 | — | — | — |
| T-mrg · merge by order | +26,855 | −327 | +26,528 | 7 of 8 | 41,281 | +180% | 1.65× |
| T-mrg · smart merge | +45,511 | −412 | +45,099 | 7 of 8 | 59,852 | +306% | 2.39× |
| T-mrg · non-conflicting | +18,595 | −221 | +18,374 | 7 of 8 | 33,127 | +125% | 1.32× |
| Global (`cand_0005`) | +11,125 | −818 | +10,307 | 7 of 8 | 25,060 | +70% | 1.00× |

For T-opt, a single champion (median over 34) adds 1,239 words (range 404–3,424), removes 3 (0–95),
changes 2 files (1–4), and totals 15,977 words.

**Definitions:** words are whitespace-separated tokens in the eight skill files (merge logs and
optimizer notes excluded). Added and removed come from a word-level diff per file, summed. A
rewritten word counts once as removed and once as added. Net = added − removed. T-opt's row sums
34 separate diffs, each counted once: it is what T-mrg had to integrate, not the size of any
deployable bundle. The T-opt and Global numbers match the paper's existing §5.4 figures.

**Comments the table needs:**
1. **Small fixes, large merge:** each task's fix is small, yet every integrated T bundle is larger
   than Global's.
2. **How much each merge kept** of the words the 34 champions added: smart merge 96%, merge by
   order 57% (a later hunk replaces any earlier hunk it overlaps), non-conflicting 39%. The smart
   merge reconciled conflicts but did not compress.
3. **Global rewrites the most:** it deletes the most Seed text (818 words) while adding the
   least. It is the only arm that rewrites existing Seed text to a noticeable extent.
4. **Size has a running cost:** per-trial agent tokens on train were 37.5k for the Seed, 59.6k for
   Global, and 52.1k / 66.3k / 88.0k for non-conflicting / merge by order / smart merge. Per-trial
   dollars were $0.124, $0.191, $0.168, $0.212 and $0.278.
5. Per-file numbers for every arm already exist (`size_table.json`) if a per-file table is wanted.

---

## 5. Table 4 — Running example: AAP2 Rule 4 ("don't re-fetch job data")

**The bug.** The Seed's AAP2 specialist says, in its Critical Rules:

> 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job metadata or
> events, extract what you need (steps, playbook events, errors) from the existing result. Do NOT
> make a redundant second call to the same job.

Its Investigation Flow, step 5, then requires a second call on the same failed job:
"If the job failed, also call `get_job_events` + `failed_only=true`". The agent resolves the
contradiction by skipping the events call, so it misses the failing task's `role`, which only the
events carry. Training task `platform-004` exposes this: Seed 0.760 over 10 trials. The same fix
was found on v4 and merged upstream as **rhpds/parsec PR #57** (2026-10-14), which shows what a
reviewed human fix of this bug looks like.

### Table 4a — word counts (main text)

Rule 4 is the numbered item itself. "Job-read guidance" is any dedicated section that says which
job action returns which field: "Choosing the job read", "`get_job_log` vs `get_job_events`",
"What the log carries vs. what the events carry", and "`get_job` is the FIRST read". Words are
whitespace tokens; added/removed come from a word-level diff against the Seed's Rule 4, as in
Table 3.

| Arm | Rule 4 | Rule 4 words (added / removed) | Contradictory Seed sentence still present? | Job-read guidance elsewhere (words) | platform-004, train |
|---|---|--:|:-:|--:|--:|
| Seed | original | 39 | yes | 0 | 0.760 (10) |
| PR #57 (upstream, from v4 T-opt) | rewritten | 111 (+94 / −22) | no | 0 | — |
| **Task-wise (T)** | | | | | |
| T-opt (`platform-004` champion) | rewritten | 74 (+59 / −24) | no | 504 | 1.000 (5) |
| T-mrg · merge by order | Seed text + appended exception | 102 (+63 / −0) | **yes** | 1,263 | 1.000 (5) |
| T-mrg · smart merge | rewritten, 3 tasks' exceptions folded in | 232 (+219 / −26) | no | 1,682 | 1.000 (5) |
| T-mrg · non-conflicting | **unchanged** | 39 (+0 / −0) | **yes** | 1,263 | 1.000 (5) |
| **Global (G)** | | | | | |
| Global (`cand_0005`) | **unchanged** | 39 (+0 / −0) | **yes** | 233 | 0.912 (4) |

The last column is mean reward over valid trials (count in brackets). For Global it is its train
incumbent sweeps. For T-opt it is the champion's own 5-trial evaluation, which selected it.

### Table 4b — the texts (supplement)

Verbatim; emphasis as in the source. Only the Rule 4 item is shown, plus a one-line pointer to
where the arm's other job-read guidance sits.

**Seed** (39 words):
> 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job metadata or
> events, extract what you need (steps, playbook events, errors) from the existing result. Do NOT
> make a redundant second call to the same job.

**PR #57, upstream** (111 words):
> 4. **Don't re-fetch job data — but a different `action` is not a re-fetch.** If a prior
> `query_aap2` call already returned what you need, read it from that result instead of asking
> again. A call is redundant only when it repeats the **same `action` with the same arguments**.
> Different actions on one job are complementary: `get_job_log` returns the log text,
> `get_job_events` returns the structured failed-task rows (`role`, `play`, `task`, `host`,
> `error_msg`), and neither response contains the other's data — so "I already queried this job"
> is not a reason to skip a different action on it, including the `get_job_events` +
> `failed_only=true` call required by step 5 of the Investigation Flow below.

**T-opt, `platform-004` champion** (74 words):
> 4. **Don't re-fetch job data.** If a prior `query_aap2` call returned a field, read it from that
> result instead of calling again. This forbids repeating the **same `action`** on the same job —
> it does NOT cover a *different* `action`. Different `query_aap2` actions return different
> fields, so calling `get_job_events` after `get_job_log` on the same job is complementary, not
> redundant. Never skip a different-action call on the grounds that you already have "the job
> data".

*Elsewhere:* a new "`get_job_log` vs `get_job_events`" section with a field table and a worked
example (504 words), plus a required events call added to Step 1 of the job workflow.

**T-mrg · merge by order** (102 words: the Seed sentence kept, another task's exception appended):
> 4. **Don't re-fetch job data.** If a prior `query_aap2` call already returned job metadata or
> events, extract what you need (steps, playbook events, errors) from the existing result. Do NOT
> make a redundant second call to the same job.
> This applies only to a call that **returned data**. A call that timed out returned nothing to
> extract, so re-issuing it is not a re-fetch — it is the first real attempt. **One** retry of a
> timed-out call is within budget: a gap you could have closed with a single retry is not an
> acceptable gap. Do not retry it a third time.

*Elsewhere:* the "different action is not a re-fetch" idea survives only in separate job-read
sections (1,263 words), including `platform-116`'s "Choosing the job read". Step 5 of the flow
became conditional ("if the job failed and you expect a task-level error").
*Why:* three tasks edited these lines: `platform-032` (replaced Rule 4 with a "two dead calls"
rule; 20th in gain order), `platform-004` (the in-place rewrite; 25th), and `platform-158` (kept
the Seed sentence and appended a timeout exception; 34th, the highest gain). Under `-X theirs`
the last edit wins a contested region, so `platform-158`'s version stands, Seed sentence included.

**T-mrg · smart merge** (232 words; renumbered as rule 7 in the merged list):
> 7. **Don't re-fetch job data — but a different action, or a failed call, is not a re-fetch.**
> If a prior `query_aap2` call returned a field, read it from that result instead of calling
> again. This forbids repeating the **same `action`** on the same job after it **returned
> data**. It does NOT cover:
> - **A *different* `action`.** Different `query_aap2` actions return different fields, so
>   calling `get_job_events` after `get_job_log` (or `get_job` alongside either) on the same job
>   is complementary, not redundant. Never skip a different-action call on the grounds that you
>   already have "the job data" — see "Choosing the job read".
> - **A call that failed without returning data.** A tool call that returned an error, a
>   timeout, or no payload at all returned nothing to extract, so re-issuing that exact call
>   **once** is not a re-fetch — it is the first real attempt (see the transient-failure retry
>   rule in the shared context). A gap you could have closed with a single retry is not an
>   acceptable gap. Do not retry it a third time; after the retry also fails, say which call
>   failed and which specific question you therefore could not answer. Never substitute a link
>   for a value the user asked you to read: if the user asked what a file contains and the fetch
>   failed, the retry is mandatory, because handing back a URL answers none of the question.

*Elsewhere:* job-read guidance (1,682 words) and the required events call in Step 1, both
cross-referenced from the rule. The three tasks folded in are `platform-004` (different action),
`platform-158` (timed-out call, retry once) and `platform-152` (retry before reporting; never
substitute a link).

**T-mrg · non-conflicting hunks**: Rule 4 unchanged (the Seed text above). All three edits to it
(`platform-032`, `platform-004`, `platform-158`) were contested, so all three were dropped. The uncontested job-read
sections survive (1,263 words), so the bundle carries the prohibition and its exceptions in
different places.

**Global, `cand_0005`**: Rule 4 unchanged (the Seed text above).
*Elsewhere:* step 4 of the Investigation Flow now points to a new "Choosing the job read" section
(233 words), which opens: "`get_job`, `get_job_log`, and `get_job_events` return DIFFERENT data
about the same job. Calling more than one of them is not a redundant re-fetch — pick by what the
question needs, and issue them in parallel", and says of the events call: "**Call this for every
failed job**".

### What Table 4 shows (comments for the text)

1. **Two ways to fix the same bug in English.** *Repair in place*: T-opt and PR #57 rewrite Rule
   4 so the contradiction disappears. *Override elsewhere*: Global leaves the rule and adds a
   later section that contradicts it. Both work on `platform-004` (1.000 vs 0.912). The in-place
   fix is a 10-line change a reviewer can read and upstream as is: it is what PR #57 is.
2. **Two ways to integrate several fixes.** The smart merge integrated by meaning: one rule
   carrying all three tasks' exceptions, with no contradiction left. Merge by order integrated by
   text position: the highest-gain edit to those lines won (`platform-158`), and it was written
   against the Seed sentence, so the prohibition stayed and the "different action" exception landed in
   another section. Non-conflicting hunks dropped all three contested edits.
3. **The prompt no longer has to be consistent to score.** Three of the five arms (merge by
   order, non-conflicting, Global) keep the contradictory Seed sentence, yet every arm's bundle
   reaches 0.91–1.00 on `platform-004`. This is the paper's interpretability point made concrete: the
   score cannot tell an in-place repair from an override, but a reviewer can.
4. **Size.** The rule itself stays small (39–232 words) in every arm. The job-read guidance around
   it ranges from 233 words (Global) to 1,682 (smart merge), which repeats Table 3's pattern at
   the scale of one rule.
5. **Upstream status.** PR #57 came from the v4 T-opt edit; the v6 T-opt edit is near-identical
   in content. The paper may say that this repair was merged into the maintained PARSEC system
   (already allowed by the handoff, `paper_notes.md` §3.5).

The supplement's existing two-column Rule 4 table (T-opt vs Global) becomes Table 4b. The
failed-event retrieval rates already in the paper (22% → 41% on test, 20% → 29% on validation)
belong to Global only and stay as they are.

---

## 6. Supporting results (text or supplement)

### 6.1 How much of T-opt's local gain survives integration (train)

On the 34 optimized train tasks the Seed scores 0.788 and every T-opt champion 1.0 (+0.212).

| | Δ on the 34 optimized tasks | share of T-opt's gain kept | Δ on the 33 tasks T never touched | of those 33, tasks down > 0.1 |
|---|--:|--:|--:|--:|
| Smart merge | +0.199 ± 0.023 | 94% | −0.046 ± 0.020 | 6 |
| Merge by order | +0.154 ± 0.028 | 73% | −0.013 ± 0.008 | 1 |
| Non-conflicting | +0.114 ± 0.024 | 54% | −0.016 ± 0.010 | 2 |
| Global | +0.124 ± 0.026 | (59%) | −0.020 ± 0.014 | 4 |

The smart merge keeps almost all of the local gain but costs the most on tasks no edit was written
for. Dropping contested hunks loses about half the gain. (Global's percentage is shown in brackets
because Global did not start from the T-opt champions.)

### 6.2 Per-task movement on test (release-gate question)

| | tasks up > 0.05 | tasks down > 0.05 | worst task (Δ) |
|---|--:|--:|---|
| Merge by order | 34 | 10 | platform-141 (−0.27) |
| Smart merge | 31 | 13 | platform-135 (−0.37) |
| Non-conflicting | 25 | 18 | platform-141 (−0.62) |
| Global | 27 | 6 | platform-131 (−0.40) |

Every deployable bundle has at least one severe per-task regression, so the paper's release-gate
point applies to both paths, not only to Global. The T merges move more tasks in both directions.
Global's platform-131 regression is much milder under the smart merge (−0.04) and merge by order
(−0.13).

### 6.3 Routing-gap tasks (outside the editable surface)

Nine test tasks are sent by the regex fast router to a specialist that lacks a required tool. Every
arm is slightly negative on them and positive on the other 57:

| | 9 routing-gap tasks | other 57 |
|---|--:|--:|
| Merge by order | −0.032 | +0.058 |
| Smart merge | −0.023 | +0.051 |
| Non-conflicting | −0.006 | +0.018 |
| Global | −0.025 | +0.047 |

This supports the paper's existing claim that skill optimization cannot repair the router.

The Rule 4 running example is Table 4 (§5).

---

## 7. Caveats to carry into Limitations

1. **The Seed was not re-measured for T-mrg.** T-mrg was evaluated on 2026-10-21. Its Seed
   reference is the Global run's Seed: train on 2026-10-16, validation on 2026-10-17, test on
   2026-10-18. Global's bundle and Seed were measured during the same run. Drift in the simulator,
   gateway or target model between those dates would bias T-mrg's Δ but not Global's. A same-day
   5-trial Seed run on test would cost about $40–80 and remove this confound; recommended before
   submission.
2. **Three methods, one test split.** All three merges were scored on the same sealed test split,
   so no method may be presented as chosen because it scored best there. Report all three, or name
   one as primary for an a-priori reason (merge by order is the natural no-judgment baseline). To
   select a single method by a held-out rule, score all three on validation (about $55–95 per
   method at 5 trials).
3. **No validation gate on T-mrg.** The merges are static and ungated. That they match Global on
   test is a result, not part of the protocol. The paper may note, carefully, that Global's
   validation-gated search did not beat ungated T-mrg on test in this run.
4. **One run per arm:** one T-opt run, one Global optimizer seed, one smart-merge run. The
   historical v4 pilot merge failed. v6 differs in task count, the per-task protocol and the
   merge methods, so v4 and v6 are not a replication. Keep v4 out of the main narrative as before.
5. **Errored trials** are left out, never scored as zero. These tasks have fewer than 5 trials:
   - Merge by order: train `cost-407` (3).
   - Smart merge: test `cloud-026` and `platform-114` (4 each).
   - Non-conflicting: train `cloud-057` and `cloud-074`, test `cloud-027` (2 each).

---

## 8. Paper locations that need to change (as of `main` at 4fef9ff)

- **Title:** "…and the Integration Challenge" reads differently now; consider whether integration
  is still the "challenge" or now one of the findings.
- **Abstract:** replace the green T-mrg sentence; the abstract can now give the T-mrg test number
  next to Global's and the cost comparison.
- **Introduction:** the green paragraph after the arms description, and contribution 2's green
  sentence.
- **§3.2, execution and optimization data flow:** resolve the BC comment with the protocol in §1.
- **§4.3:** the Table 2 (scope) row for T-mrg; the "Task-wise path" paragraph's last sentence;
  the "Comparison scope" paragraph (T-mrg now has a test evaluation).
- **§5 Results:**
  - Table 1 (`tab:overall`): replace with Table 1 above.
  - The "Why the pending merge matters" paragraph: replace it with the T-mrg result.
  - §5.3 cost table (`tab:cost`): replace with Table 2 and update the compute-hour figures.
  - §5.4 skill size: add the merged bundles (Table 3).
  - §5.5 running example: use Table 4a in the main text and Table 4b in the supplement; Table 4b replaces the supplement's existing two-column Rule 4 table.
- **§6 Discussion and Conclusion:**
  - The "four bounded conclusions": the fourth is now answered.
  - "Optimization scope should match deployment scope": still true. A static merge evaluated as
    one artifact is exactly that.
  - Limitations: T-mrg is no longer unfinished; add the caveats in §7.
  - Conclusion paragraph.

---

## 9. Sources

In `parsec-history` (this branch): `results/v6/v6_t4_e1/`, `artifacts/v6/v6_t4_e1/`, `results/v6/v6_t2_e1/`, `artifacts/v6/v6_t2_e1/`, `ui/v6_tables_*.html`. Code: `examples/parsec/v6_t4/`, `v6_t2/` on `main` (skillberry-ai/cap-evolve#904). The table below gives paths in the source `parsec-intake_v6-t2` worktree

| What | Where (relative to the worktree) |
|---|---|
| T-mrg plan and blind rule | `examples/parsec/v6_t4/PLAN.md` |
| Merge inputs (Seed, 34 diffs, scrubbed rationales) | `results/v6_t4_e1/merge_inputs/` |
| Frozen merged bundles + merge logs | `results/v6_t4_e1/{m1_order,m3_smart,m2_nonconflict}/` (m1 = merge by order, m3 = smart, m2 = non-conflicting) |
| Merge time, tokens, cost | `results/v6_t4_e1/merge_cost.json`, `m3_smart_usage.json` |
| Pooled 5-trial rewards | `results/v6_t4_e1/eval/v6t4_{m1,m3,m2}_5t.json` |
| Table 1 analysis (deltas, CIs, subsets, head-to-head) | `examples/parsec/v6_t4/analyze_t4.py` → `results/v6_t4_e1/eval/analysis*.json` |
| Table 2 | `examples/parsec/v6_t4/cost_table.py` → `results/v6_t4_e1/cost_table.json` |
| Table 3 | `examples/parsec/v6_t4/size_table.py` → `results/v6_t4_e1/size_table.json` |
| Table 4 | `examples/parsec/v6_t4/rule4_table.py` → `results/v6_t4_e1/rule4_table.json` (each arm's Rule 4 verbatim, word counts, platform-004 reward) |
| Rendered tables (HTML) | `results/v6_t4_e1/{main_table,cost_table,size_table}.html` |
| Narrative report | `results/v6_t4_e1/README.md` |
| T-opt run (unchanged) | `results/v6_t2_e1/` |
| Global run (unchanged) | v6_g2_e1, PR skillberry-ai/cap-evolve#887 |

Global's validation reward for `cand_0005` is computed from the sealed validation rollouts of the
Global run: tag `r004__cand_0005__seq*` for the candidate and `final__seed` for the Seed.
