# PROCESS — what I did this iteration (explainability; REQUIRED)

**Candidate `cand_0002`. Parent: `cand_0001`'s prompt files (champion is still `seed`).**
Iteration 2 of 2 — final iteration of the run.

## 0. The decision that framed everything: what the gate actually said

`cand_0001` scored val **0.871 vs seed 0.830 (Δ +0.0605)**, `broke={}`, `fixed={icinga-204,
platform-126, platform-158}`. It was rejected at the P2 confirmation stage
(`events.jsonl`: `delta_full 0.0605`, `se_full 0.0601` → z ≈ 1.0; rung-1 paired z = 0.60;
`joint_coverage 0.179`). **Δ was almost exactly one standard error.** Nothing regressed.
The RESULT stamp's own reading: *"the lever is POWER or SIZE, not a redesign — keep the
edits that produced the `fixed` tasks as your starting point; do not rewrite them."*

So I did NOT restart from `seed`. I copied `cand_0001`'s eight files in as my base
(preserving the three measured fixes) and spent the whole iteration making the effect
**bigger** and **repairing cand_0001's own defects**. Structural difference from the
rejected candidate (required by CLAUDE.md): a new top-level failure class it never
addressed (the conclusion checklist, ~26 tasks of loss), plus three in-place repairs of
cand_0001 text that my diagnosis showed was actively teaching the wrong behaviour.

## 1. Ranked issue list (re-clustered from scratch this round)

Method: all 670 baseline rollouts carry a full `verifier/reward-detail.json` (reachable via
`rollout.metadata.trial_dir`). I joined every trial's **missed rubric items** (with their
accepted `any_of` strings) to its transcript, then clustered by mechanism. Totals across
the 284 near-miss trials: **derived conclusions 227 misses / 26 tasks**, tool calls 118/19,
literal values 64/15, forbidden hits 39/12. The loss is overwhelmingly *unstated
conclusions*, not missing data.

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Conclusion never stated as a sentence** | ~10 directly, ~26 touched (402, 124, 051, 101, 045, 201, 317, 139, 117, 119) | The right fact is in a table cell, a column/section heading, a label (`None`, `N/A`, "data gap"), or a synonym. cand_0001's answer rule covered **yes/no questions only**; the misses are on "what to do", "explain why", "what is the utilisation", "how many". | BEHAVIORAL | new checklist in `shared_context.md` |
| 2 | **Line number asked for, omitted or miscounted** | 5 (152, 153 at 10/10; 104 at 9/10; 101, 136 at 6–7/10) | `fetch_github_file` returns no line numbers. Two sub-modes: no number at all (quotes the text), or ±1–3 from skipping `---`/blank/comment lines. | KNOWLEDGE | repair cand_0001's rule in place |
| 3 | **Epoch mis-converted; elapsed time wrong or absent** | 5 (215, 204, 216, 206, 212) | Converted by eye → off by hours or a whole month, inverting every "still in effect / how long ago" verdict. cand_0001's anchor table is **verified correct (36/36 anchors)** and demonstrably works, but its elapsed procedure required converting "now" *into* an epoch — the step that fails. | KNOWLEDGE | repair + extend `icinga_agent.md` |
| 4 | **Answer voices a refuted premise / un-reached state / trap figure** | 12 tasks, 39 forbidden hits | A heading reusing the user's premise; a trap ratio computed then caveated; a future state named as a bare noun. | BEHAVIORAL | extend the refutation rule |
| 5 | **Result doesn't mean what was asked; error read as zero** | 5 (408, 418, 402, 407, 051) | An `{"error": …}` worded like an empty result filed as `$0`; a clamped `period` re-derived from the parameters sent; an unfilled roll-up explained as a "data gap". | KNOWLEDGE | action rules in `cost_agent.md` |
| 6 | **Fast-path routes to an agent with no tool for the data source** | 6 (304, 315, 074, 310, 071, 013) — **~3.5 task-points, the single largest** | `classify_fast()` dispatches on topic words before the orchestrator LLM; the matched agent has no tool for the task's data source and cannot hand off. | CAPABILITY-GAP | **SKIPPED — unreachable by prompt** |

## 2. Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL / CONTRACT | `shared_context.md` (new, at the top) | "Before you send the answer: the conclusion checklist" — six lines, one per conclusion *shape*: absence, how-many/how-much, number-vs-limit, not-a-measurement, remedy, per-entity enumeration. Plus: a table cell/heading/label never counts as stating a conclusion, and no formatting marker inside a conclusion phrase. Generalizes because it is keyed to the **shape of the question**, not to any domain: every task in this suite is graded by substring rubrics over the same answer surface. | item 1 carves out masked/redacted values (platform-036); item 2 carves out mismatched windows (cost-418 forbidden share) and requires tallying rows before writing a count (icinga-015) |
| 2 | KNOWLEDGE | `shared_context.md` | Rewrote "Citing a line in a file": cite the line that **carries the value asked about, even when nested**; cite a block's opening line when the question is about the block; cite **both** lines when the fault is a relationship between two; count from line 1 (or a log anchor), write every row including `(blank)`, never `...`, never start from an estimated number. Worked example rebuilt to start at line 1. | no protected task asks for a line number |
| 3 | KNOWLEDGE | `icinga_agent.md` | Completed the epoch field list; replaced the elapsed procedure with **calendar subtraction** (never build an epoch for "now"); days-vs-hours unit rule; "put the converted time in the answer"; `0` = not set described as a field fact, not a global claim. New worked example verified with python. | "every converted time" narrowed to *timestamps the question turns on* (icinga-214 converts none) |
| 4 | BEHAVIORAL | `shared_context.md` | Never name a state/event/escalation that has not happened as though it had; state the held state first and the pending one only as a consequence; say an action has not been taken rather than describing when one would be. | kept narrow to un-reached states; the pre-existing heading rule was left untouched |
| 5 | KNOWLEDGE / ACTION | `cost_agent.md` | (a) an `{"error"}` result is a failed call however gently worded — scoped to *queries you draw figures from*, with a carve-out for render/format tools; a partial sum must name what it covers and excludes and must not be led with as the total. (b) Copy `period.start`/`period.end` verbatim, compare windows before dividing, same days → divide normally. (c) Placeholder zero → say not measured, then call the preset that does measure it, *unless the user restricted you to one query*; if that call is empty the figure stays not measured. Removed the opt-out clause ("which happens on historical-data retries") that let the agent decide a standing warning did not apply. | render carve-out protects cost-073/cloud-307; "same days → divide normally" protects cost-028/416 |

Deliberately **reverted** mid-iteration: an added carve-out on the job-log file-path
shortcut. The pre-ship check showed it would have forced an extra `search_github_repo`
into protected platform-070 in ~9/10 trials. Dropped entirely; only the neutral
"fetch it directly" wording remains.

## 3. Verify-the-fix (per change: the trace it targets → what the new text does on those exact inputs)

- **Checklist #4 → cost-402 (10/10 missed `zeros-not-measured`).** Baseline t0 calls the
  `0.0` roll-ups "a data gap in the cache". The rule names that exact substitution and
  splits placeholder-zero from absent-field, so the two cases get different (and
  rubric-accepted) wordings. Verified WOULD-FIX.
- **Checklist #1/#3 + no-marker-inside-the-phrase → platform-101 (`why-over`, 5/10).**
  Baseline t1 wrote "requests **76 vCPUs** against a **64 vCPU**" — the facts were present
  and the bold split the phrase. The formatting rule targets exactly that; a verifier
  subagent scored the template wording against the task's own `verify.py` and it passes.
- **Checklist #1 → icinga-201 (`not-notified`, 3/10).** Baseline t7 wrote "Notifications
  are only sent on a HARD state" — a condition, not a statement that none was sent.
  "Use the question's own verb" yields "has not sent out a notification yet"; scored
  against `verify.py`: passes.
- **Line-citation rewrite → platform-152/153 (10/10 each).** Baseline t0 wrote "the last
  line of the file"; every platform-153 trial quoted the line with no number. The rule
  forbids both forms and requires "line N". Counted independently with python: the
  procedure lands on 17 and 13, the rubric's values.
- **Line-citation rewrite → platform-136 (line 15) and platform-104 (line 38).** These
  pull opposite ways — 136's target is a property nested in a task, 104's is a resource
  declaration. The first draft of my rule said "never cite a nested property", which would
  have sent 136 to the wrong line; the pre-ship check caught it. The shipped rule keys on
  *what the question asks about*, and the cite-both-lines clause covers 104's
  declaration-vs-reference pair. Both counts re-verified by hand with python.
- **Epoch edits → icinga-215/216/206/212.** Every graded epoch converts exactly through the
  table (re-verified: 1795802400 → 2026-11-27 18:00; 1795298400 → 2026-11-21 22:00;
  1794190500 → 2026-11-09 02:15; 1794752400 → 2026-11-15 14:20). Baseline was wrong in
  essentially every trial (one month early plus random hours). The "put the converted time
  in the answer" rule targets the ~6 icinga-206 trials that printed only the raw epoch.
- **Elapsed rule → icinga-204 (`hours-since-end`, 10/10) and icinga-206 (`days-stale`,
  8/10).** Baseline icinga-204 t5 built an epoch for "now" and got `1763982600` — a year
  off; icinga-206 t3 measured from the system date (2026-10-16) against a November event.
  Calendar subtraction removes the first failure mode and "now is whatever the user says"
  removes the second. **Evidence this fires:** cand_0001's own icinga-204 rollout used the
  table, self-corrected an anchor slip, and scored 1.0 — and the LEDGER lists icinga-204 as
  measurably `fixed`.
- **cost edits → cost-408 (7/10).** The GCP call returned `{"error": "... query failed: no
  matching cost data"}` and t0 charted it as `$0.00`, headlining a two-provider sum as the
  total. The new step 4/5 reclassify that result and force the partial label.
- **cost edits → cost-418 (10/10 + 7/10 forbidden).** `period` was 2026-11-16 → 2026-12-02
  against monthly rows; t0 re-derived the start as "Nov 1", t2 published "2.4% raw" plus a
  pro-rated figure. Copy-the-period-verbatim plus the don't-divide branch target both.

**Honest negatives** (a verifier subagent judged these WOULD-NOT-FIX and I did not chase
them, because the only way to close them is to write a task's accepted phrasing into the
prompt):
- platform-124 `b-action` — the rubric accepts a narrow set of phrasings; my subject-first
  wording lands near but not inside it. I changed the rule to subject-first negation
  because that is better English for an absence, not to match the string.
- platform-116 `slowest-success` — needs the figure as bare digits; cand_0001's "Stating
  Numbers" rule already covers it and I cross-referenced it from checklist #2.
- cost-051 — "not measured" is the wrong register for a field the tool never returns, which
  is why checklist #4 now splits the two cases.

## 4. Process & features used

- **Subagents:** 5 parallel read-only diagnosis subagents (one per mechanism cluster), then
  1 edit subagent on `cost_agent.md` (the only independently-editable file) while I edited
  `shared_context.md` and `icinga_agent.md` directly, then **2 parallel adversarial
  reviewers blind to my rationale**, then 1 pre-ship checker on the specific defects they
  found. No worktrees: the edit surface is 3 files and serial editing of the shared file
  avoided merge conflicts entirely.
- **The review fan-out was again worth more than the diagnosis fan-out.** It found 11
  defects, of which 6 were regressions on *named protected tasks* that my own draft would
  have caused, 1 was a rule that would have sent a task to the wrong line, and 1 was a
  graded-answer value (`76`/`64`) I had written into an example. The pre-ship checker then
  refuted 2 of my 6 fixes, and I changed the text again. I would have shipped a worse
  candidate without these three passes.
- **Leak audit as a gate:** I extracted every literal from the diff and cross-checked it
  against the 67 feedback tasks' `golden.json` + `tests/`. Three real leaks found and
  removed (`76`/`64` = platform-101's values; `$900` = platform-148's graded TTL; the
  verbatim error text `"no matching cost data"` = cost-408's seeded string; plus
  `2025-03-01`, a near-collision with cost-407's period end). Final audit: every remaining
  literal is a tool field name, an arithmetic constant, or an invented value absent from all
  feedback task material.
- **I did not read `.capevolve.sealed/` or the hidden `test` split's task definitions**,
  although both are readable from this working directory and `splits.json` lists all 66
  hidden task ids by name. Tuning to them would manufacture exactly the non-transferable
  gain this round exists to detect. Flagged as a leak in FRAMEWORK_IMPROVEMENTS.md.
- **Prior iterations read:** `RUNMAP.md`, `prior_iterations/cand_0001/{PROCESS.md,diff.patch}`,
  `LEDGER.md`, the whole `JOURNAL.md`, `INSIGHTS.md`, `META_INSIGHTS.md`,
  `rejected.jsonl`, and the raw `events.jsonl` promotion records. What I took from them:
  (a) the Δ-vs-SE arithmetic that says cand_0001 failed on power, not on damage;
  (b) the verified fact that 53/67 tasks never read `orchestrator.md` — so I made **zero**
  edits there; (c) the verified fact that cluster 6 is unreachable, so I skipped it;
  (d) cand_0001's list of carve-outs protecting named passing tasks, which I preserved.

## 5. Good things to PRESERVE (do not let a future iteration undo these)

- **The epoch anchor table in `icinga_agent.md`.** Re-verified 36/36 anchors. It is credited
  with the measured fix of icinga-204, and a cand_0001 rollout shows a sonnet-tier reader
  executing it correctly after one self-corrected slip. Do not move it to
  `shared_context.md`: a scan of all non-icinga trajectories found **zero** epoch integers
  in tool results — every other domain returns ISO-8601.
- **The three false-baseline-rule corrections from cand_0001** (`get_job` vs `get_job_log`;
  `fetch_github_file` does not list directories; `search_aap2_logs` takes the short name).
  Each maps to a 9–10/10-trial unmatched expected call, and two of the three measured fixes
  trace to them.
- **The carve-outs, each of which protects a named passing task:** masked/redacted ≠ absent
  (platform-036); mismatched windows suspend the arithmetic (cost-418); tally before stating
  a count (icinga-015); render/format tool failures are not reportable query failures
  (cost-073, cloud-307); "same days covered → divide normally" (cost-028, cost-416);
  convert only the timestamps the question turns on (icinga-214); "unless the user
  restricted you to one query" (cost-402).
- **The neutral wording of the job-log path shortcut.** I added a carve-out there and then
  removed it after evidence it would change platform-070's trajectory. Do not re-add it.

## 6. Deliberately skipped

- **Cluster 6, the fast-path tool gap (~3.5 task-points, the largest single cluster).**
  Verified unreachable: the required facts live behind a tool the dispatched agent does not
  have, and sub-agents cannot hand off. Confirmed again this round — cloud-315's answer is
  literally "I don't have access to an AWS Marketplace agreement inventory through any of
  the tools available to me". Needs a code change to `classify_fast()`; escalated.
- **Relocating `shared_context.md`'s rules into domain files (the dilution hypothesis).**
  META_INSIGHTS named this as the next test if cand_0001 was rejected *without a clear
  per-task cause*. I chose not to: the gate's evidence is that cand_0001 did no damage and
  simply lacked power, so moving working text around would spend the last iteration on a
  reorganisation with no expected gain while risking the three measured fixes. I put the new
  material at the **top** of the file instead, where prominence is highest, and kept the new
  cost rules in `cost_agent.md` rather than the shared file. The hypothesis remains untested
  — recorded as such in META_INSIGHTS.md.
- **Chasing narrow rubric phrasings** (platform-124, cost-051, platform-116's digit format).
  Each is one task and the only reliable fix is to write the accepted string into the
  prompt. That is the overfitting the hidden stratum is built to catch.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.
