# platform-008-log-does-not-say

<!-- BEGIN:auto -->

**task:** `platform-008-log-does-not-say`  
**category:** platform  
**tranche:** regression  
**services:** platform  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.933 |
| seed (val, v4_t2_e1) | val | 5 | 0.800 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 1.000 |

delta vs JB: 0.000 · delta vs our baseline: 0.067

**T2 cost/time:** $13.83, 438,410 tokens, 1.65h (eval $1.04/322,925tok · optimizer $12.79/115,485tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310/report.md`, `.capevolve/v4_t2_e1_platform-008-log-does-not-say/run_20260920_144310/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A job is recorded as failed, and the task asks for the root cause. The seeded log genuinely ends mid-task with no error text or result line, so the correct answer is to say plainly that the log doesn't establish a cause, rather than inventing one.

## What the optimizer tried

Single iteration (`cand_0001`) rewriting `aap2_agent.md`, `shared_context.md`, and `orchestrator.md` after finding all 5 seed trials scored an identical 0.8 by missing the same graded fact (`no-root-cause`) for two different reasons: 3/5 trials fabricated a cause the evidence didn't support, and 2/5 got the right verdict but lost credit to markdown bolding breaking a literal substring match. The optimizer traced the fabrication to the prompt itself — `aap2_agent.md` said "Long = timeout," licensing a cause from elapsed time alone — and removed that licence, added a new "Does the evidence actually establish a cause?" step naming what does and does not establish a cause, added a "when no cause is established" output branch, and, after an adversarial review round caught that `orchestrator.md` never received the anti-bolding rule that lived only in the other two files, added the same plain-text formatting rule to `orchestrator.md`. This is a rerun (`run_20260920_144310`); the first attempt (`run_20260920_124829`) never finalized — its `state.json` shows 2 iterations spent and a best val of 0.96, but no `report.md`/`final.json` were ever written, due to an unrelated infrastructure interruption during that run (see `results/v4/summary.md`'s "Data-quality caveats").

## Why the winning candidate won

JOURNAL.md's `reward-detail.json` reading shows the entire 0.2 val gap was one missing substring (`no-root-cause`) split across two sub-modes (a fabricated cause vs. a correct-but-bolded verdict); the licence-removal and the plain-text formatting rule (added to all three prompt files after the audit found `orchestrator.md` was the actual site of the bolding bug in 2/5 trials) closed both, moving val 0.800 → 1.0 (Δ+0.200) and fixing the task per the RESULT line. On the held-out test split, `report.md` records the baseline `seed` skills at 0.960 ± 0.040 versus the optimized skills at 1.0 ± 0.0, a test-side improvement of +0.040.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning (see `results/v4/summary.md`'s "Coverage" section). JOURNAL.md notes the new `shared_context.md` "Reporting a Negative Finding" block is prepended to all six domain agents but was only exercised by this task's trials — the optimizer checked the other five domain files for contradictions and found none, but calls that "a reading, not a measurement."

<!-- BEGIN:diff -->

## What changed (seed → best)

3 of 8 skill files changed. Full unified diffs, [`artifacts/v4/seed/`](../../../artifacts/v4/seed/) → [`artifacts/v4/platform-008-log-does-not-say/best/`](../../../artifacts/v4/platform-008-log-does-not-say/best/):

<details>
<summary><code>aap2_agent.md</code> (+93/−8)</summary>

```diff
--- seed/aap2_agent.md
+++ platform-008-log-does-not-say/best/aap2_agent.md
@@ -11,9 +11,10 @@
    Stay silent while using tools. Only produce text when presenting actual findings.
 
 2. **ALWAYS produce a structured final report.** Your LAST text output MUST be the
-   full structured analysis (config trace table, failure analysis, root cause,
-   recommendations). If you have been calling tools, your next text block should be
-   the report — not more narration.
+   full structured analysis (config trace table, failure analysis, root cause — or,
+   when the evidence does not establish one, the explicit statement that it does not,
+   see Step 7a — recommendations). If you have been calling tools, your next text
+   block should be the report — not more narration.
 
 3. **Budget your rounds.** You have a limited number of tool calls. Do NOT
    speculatively browse directories — use `search_github_repo` or `lookup_catalog_item`
@@ -59,6 +60,11 @@
 4. Call `query_aap2` with `get_job_log` using `towerHost` as controller and `deployerJob` as job_id.
    **Always use `get_job_log` instead of `get_job`.**
 5. If the job failed, also call `get_job_events` + `failed_only=true`
+   — if this returns **zero events**, that is an *absence of a recorded reason*, not a clue
+   about which reason it was. Zero failed events is never itself evidence of a timeout, a
+   kill, or a network problem. Carry it forward as "no recorded reason" and let Step 7a
+   decide what can be concluded; do not settle on a cause here, in your narration, before
+   you have worked the config trace.
 6. Continue to trace the config hierarchy via the "Investigate AAP2 Job Failures" workflow Steps 2+
 
 **If the AnarchySubject is gone**, use `query_aap2(action="find_jobs", template_name="<guid>")`
@@ -273,14 +279,46 @@
 trace deeper to find the actual cause — what command failed, what script errored,
 what resource was missing.
 
+Tracing deeper means **fetching more evidence**, not reasoning past the evidence you
+have. If the deeper evidence is not there — no error line, no failed events, nothing
+that names a reason — the answer is that it is not established (Step 7a), not the most
+plausible cause you can construct.
+
 **Key sections to examine in the log:**
 1. **PLAY RECAP** — Summary of hosts and status
 2. **fatal** or **FAILED** tasks — Actual error messages
 3. **TASK [role_name : task_name]** — Identify which role/task failed
 4. **Pod status details** — container states, waiting reasons, restart counts, exit codes
-5. **Timing** — how long did the failing operation take? Short = auth/config error. Long = timeout.
-
-Common failure patterns:
+5. **Timing** — how long did the failing operation take? Short (< 10s) points at an
+   auth/config error; long points at a wait that never returned. Timing narrows the
+   *candidates* — on its own it is never the cause. See Step 7a.
+
+#### Step 7a: Does the evidence actually establish a cause?
+
+Do this before you write the report. A failure reason is established only when a tool
+result **states** it. You need at least one of:
+
+- a `fatal:` or `FAILED! => {...}` line, or an event with a non-empty `error_msg`;
+- an explicit error, exception, non-zero `rc`, or timeout message in the log or events;
+- a field on the job or resource record that names the reason (e.g. `job_explanation`).
+
+**A log that simply stops is not evidence of a cause.** When the log ends in the middle
+of a task with no result line for that task, no `fatal:`/`FAILED!` anywhere, and **no
+PLAY RECAP**, the log was truncated or the job was terminated from outside Ansible: it
+records *that* the job ended, never *why*. If `get_job_events` with `failed_only=true`
+also returns zero events, there is no recorded reason at all.
+
+When that is the case, do NOT promote a plausible story to a cause. In particular, **a
+long elapsed time, an exactly round duration, or a wait/poll task as the last visible
+line does not establish a timeout** — that evidence is equally consistent with the
+runner pod being killed, the controller losing the job, a dropped connection, or the
+log being trimmed before upload. Naming one of them anyway is the single most common
+way this report goes wrong. Report the absence as the finding — see **"When no cause is
+established"** in the AAP2 Output Format — and list what you would check next.
+
+Common failure patterns — each row requires its left-hand signal to be **present in a
+tool result**. Never apply a row from an absence, from timing alone, or from the name
+of the last task you can see:
 
 | Pattern | Likely Cause |
 |---------|--------------|
@@ -298,7 +336,11 @@
 
 **When the log shows a pod failing to start (CrashLoopBackOff, init container
 failures, pod never Ready), you MUST trace into the failing container to find the
-actual cause. "Pod failed to start" is never an acceptable root cause.**
+actual cause. "Pod failed to start" is never an acceptable root cause.** If the
+container's own evidence is genuinely unavailable — the log does not include it, the pod
+was already deleted, the tool returns nothing for it — then you are in Step 7a: say that
+the evidence does not establish the cause and name the container whose logs would settle
+it. A guess about what was inside the container is not a substitute for the container.
 
 1. **Identify the failing container** from the pod status in the log — is it an init
    container or main container? Note its name, image, restart count, and exit code.
@@ -413,8 +455,51 @@
 **Root Cause & Recommendations:**
 1. **Immediate cause:** what directly failed (the specific command, script, or operation)
 2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.)
-3. **Evidence:** how you determined this (timing analysis, error message, script trace)
+3. **Evidence:** the tool result it rests on — quote the `fatal:` / `error_msg` line, or
+   the specific script line, container, or file the trace lands on, plus the timing that
+   pins it (Steps 7b/7c)
 4. **Fix suggestions:** actionable next steps with specific commands or file paths
+
+**When no cause is established** (the Step 7a bar is not met): keep the rest of the
+report, and let the honest finding take the place the cause would have held. Do not omit
+it, and do not fill it with a guess dressed up as a conclusion. Concretely: the plain
+sentence below goes **first**, above the config trace, and the report then carries no
+Root Cause section at all — the finding has already been stated, so there is nothing for
+that section to hold. If the report shape you are following puts a cause in a table, the
+only permitted value in that cell is `not established` — never a hypothesis, however
+hedged (that is the third bullet below).
+
+- **Open the report with one plain sentence saying the log does not establish a cause.**
+  Write the negation as contiguous plain words — `does not establish`, never
+  `does **not** establish`. Emphasis inside the phrase turns your main finding into an
+  aside and breaks it for anyone, or anything, scanning the report for the verdict.
+- Then give **What the log does show** — the tasks that ran and their results, plus the
+  specific artifacts that are *absent* (no `fatal:` line, no PLAY RECAP, zero failed
+  events). Name the absences; "nothing found" is not specific enough.
+- State any hypothesis as a hypothesis — "consistent with …", "would explain …". Never
+  present it as a Root Cause heading, a **Root cause** table row, a bolded verdict line,
+  or a "most likely cause" label, and never write "the root cause is/was …" for something
+  no tool result states. Re-labelling a guess "most probable" does not make it a finding.
+- Then give **What I would look at next**, ordered, naming the specific tool, action, or
+  field for each step.
+
+<example>
+The log does not establish a root cause for job {id}.
+
+**What the log does show:** the play gathered facts, `TASK [{task}]` completed, then it
+entered `TASK [{last_task}]` and stops there. There is no result line for that task, no
+`fatal:` or `FAILED!`, no error text, and no PLAY RECAP. `get_job_events` with
+`failed_only=true` returned zero events. The job is recorded as failed after {elapsed},
+which is consistent with that task never returning — but the log itself does not say why.
+
+I am not naming a cause on that evidence.
+
+**What I would look at next:**
+1. `get_job_events` with `failed_only=false` — the full event stream sometimes carries an
+   error the stdout never received.
+2. The job record's `job_explanation` field — where AAP puts a runner-level failure.
+3. AAP2 controller logs in Splunk around the finish timestamp, if the events are empty too.
+</example>
 
 **Relevant Files to Review:**
 - AgnosticV config: `{path_to_common.yaml}`
```

</details>

<details>
<summary><code>orchestrator.md</code> (+16/−1)</summary>

```diff
--- seed/orchestrator.md
+++ platform-008-log-does-not-say/best/orchestrator.md
@@ -19,7 +19,10 @@
 
 Use tables for structured data. Use bullet points for lists. Keep explanations
 short. If the user asks "why did this fail?", answer with the cause — not a
-walkthrough of how you figured it out.
+walkthrough of how you figured it out. If the retrieved data does not establish a
+cause, then "the data does not establish one" IS the answer: state that plainly in one
+sentence and say what you would check next, rather than offering the most plausible
+cause you can construct.
 
 Be concise and data-driven. Show exact numbers and dates. Use markdown tables for
 tabular data. Stay measured and objective — present facts and let the investigator
@@ -164,6 +167,18 @@
 introduces errors (wrong links, missing config trace), and wastes the user's time
 re-reading what they already saw.
 
+**Never upgrade the agent's verdict.** If the agent reported that the evidence does not
+establish a cause, your follow-up must not state or imply that one was found — no "the
+root cause has been identified", no "the investigation confirmed …". Leave the question
+open as the agent left it, and offer the agent's own next steps as the `{{choices}}`.
+
+**If you write a negative finding at all, write the negation as contiguous plain words.**
+`does not establish`, `does not say`, `cannot determine` — never split the phrase with
+emphasis, as in `does **not** establish`. Emphasis inside the phrase demotes the main
+finding to an aside and breaks it for anyone, or anything, scanning the text for the
+verdict. This holds for every line you author: a one-line preamble above the agent's
+report, a follow-up suggestion, and the label on a `{{choices}}` button.
+
 ## Stay Focused on the Current Investigation
 
 **CRITICAL: When investigating a specific sandbox, account, or user, ONLY
```

</details>

<details>
<summary><code>shared_context.md</code> (+30/−1)</summary>

```diff
--- seed/shared_context.md
+++ platform-008-log-does-not-say/best/shared_context.md
@@ -8,7 +8,10 @@
 
 Use tables for structured data. Use bullet points for lists. Keep explanations
 short. If the user asks "why did this fail?", answer with the cause — not a
-walkthrough of how you figured it out.
+walkthrough of how you figured it out. If the data you retrieved does not establish a
+cause, then "the data does not establish one" IS the answer: state that plainly in one
+sentence and say what you would check next. A confident-sounding guess is a worse
+answer than an accurate negative one.
 
 ## Provision Database
 
@@ -212,6 +215,32 @@
 - If you are unsure about a detail and no tool result confirms it, say "not confirmed
   by available data" rather than guessing.
 
+### Reporting a Negative Finding
+
+Absence of evidence is a legitimate, complete answer. When the question asks for a
+cause, a reason, an owner, or a verdict and **no tool result states one**:
+
+1. **Lead with one plain sentence naming what was not established** — e.g. "The log
+   does not establish a root cause", "The data does not show which user held the
+   account at that time." Write the negation as contiguous plain words:
+   `does not establish`, **not** `does **not** establish`. Markdown emphasis inside the
+   phrase demotes your main finding to an aside and breaks it for anyone, or anything,
+   scanning for the verdict.
+2. **Then give the evidence, including what is missing** — name the specific absent
+   artifact (no error line, no recap, zero rows, empty event list), not just
+   "nothing found".
+3. **Label every inference as an inference** — "consistent with …", "would explain …".
+   Do not present it as a heading, a table row, or a bolded verdict line that asserts it
+   as the answer, and do not write "the cause is …" / "the root cause is …" for something
+   no tool result states. Re-labelling a guess "most likely" or "most probable" does not
+   turn it into a finding.
+4. **Say what you would check next**, ordered, naming the specific tool, action, or
+   field for each step.
+
+Do not soften a negative finding into a positive-sounding one, and do not pad it with a
+speculative cause so the report looks complete. An accurate "not established" plus a
+concrete next step is a full answer, and it is the answer the investigator can act on.
+
 ## Confidence Markers
 
 When your response includes inferences, extrapolations, or conclusions not directly
```

</details>

<!-- END:diff -->
