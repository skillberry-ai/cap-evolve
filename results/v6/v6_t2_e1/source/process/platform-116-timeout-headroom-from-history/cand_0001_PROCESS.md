# PROCESS — what I did this iteration (explainability; REQUIRED)

## Method note: I measured my hypotheses before editing

The 10 seed trajectories in `./trajectories/` carry only a scalar reward, so I went to
each trial's `trial_dir` and read `verifier/reward-detail.json` + `agent/agent.jsonl`.
That gives the **exact** `required_missed` / `counts_missed` / `forbidden_hit` ids per
trial and the exact tool-call sequence. I then imported the task's own
`tests/verify.py` and re-ran its matchers over the 10 stored answers, so every
mechanism below is a measured fact about this champion, not a reading of the prose.
The same harness let me score a candidate answer written as my edited prompts
instruct — **reward 1.0 (tool_calls 1.0, answer 1.0)** — before committing.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Wrong job-read action** — `tool_calls` capped at 0.5 in **9/10** trials. `get_job` (the expected first call) was never issued; the agent opened with `get_job_log`, whose `log` is `""` for this job. `aap2_agent.md` said, in three places, "**Always** use `get_job_log` instead of `get_job`" — a blanket rule that is wrong for an outcome/timing question. | platform-116 | A blanket tool preference overrides per-question tool selection; the metadata-only action is never reached. | BEHAVIORAL | Replace the blanket rule with a discriminating selector keyed on what the question needs |
| 2 | **Converted numbers lose the raw value** — `slowest-success` (5320) missed in **10/10** trials; `limit` (5400) missed in 1. Not a reasoning failure: the agents *had* the number and wrote it as `5,320` / `1h 28m 46s`. The verifier's `_count_present` deliberately rejects a digit run split by a thousands separator. Stripping only the commas from the 10 stored answers flips `slowest-success` to satisfied in **6/10** with no other change. | platform-116 | Style guidance ("Show exact numbers") never says *in the unit the tool returned, unseparated*; agents reflexively prettify. | BEHAVIORAL | Output-contract rule: raw value + unit at least once, conversion allowed *in addition* |
| 3 | **Denying a cause coins it** — forbidden `invented-task-failure` hit in **5/10** trials. Every hit is a *correct denial* whose wording names the failure mode: "zero **failed task** events", "it wasn't a code bug or a cloud **API error**". The contract excuses only specific refutations ("no task failed", "not a task failure"); naming a mode in order to negate it scores as asserting it. | platform-116 (117 and 159 share the trap) | No rule tells the agent to describe an absence *as* an absence rather than as a named-and-negated cause. | BEHAVIORAL | Phrasing rule: state the observed cause; never coin a failure mode to put "not" in front of it |
| 4 | **Headroom left implicit; read-only left unsaid** — `margin` (80) missed in 4/10; required `read-only` missed in 2/10. The margin was written as "zero", "a margin of zero", "~33% buffer" — never as the subtraction 5400−5320. And 2 trials named the AAP2 admin to ask *without ever saying they could not make the change themselves*. | platform-116 | The derived comparison and the explicit "I cannot" are both unstated obligations. | KNOWLEDGE | Compute-and-state checklist for limit-vs-history; mixed-request read/decline contract |
| 5 | **Wasted config-chain calls** (cost/latency, not reward) — the "MANDATORY `fetch_github_file`" rule drove `lookup_catalog_item` → `search_agnosticv_prs` → GitHub sweeps that returned `found:false` / `count:0` in every trial. | platform-116 | A mandate written for config-caused failures fires on a failure whose cause is in the job metadata. | BEHAVIORAL | Scope the mandate with an exception + a stop rule |

## Changes made this iteration

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL (decision policy) | `aap2_agent.md` — new "Choosing the job read"; two Tips lines and the Investigation-Flow step rewritten to defer to it | States that the three actions return *different* data and selects by need: `get_job` for timing/outcome/`job_explanation`, `get_job_log` for log text, `get_job_events` for the failing role/host. Adds "when a job's own metadata already states the cause, that is the cause". Any task asking *did it finish / how long / was it stopped at a limit* now reaches the metadata action. | **Yes — checked across all 200 suite tasks.** 44 expect `get_job_log`, 4 expect `get_job`, **0 forbid either**. The discriminator matches the data: every `get_job_log` task's instruction says "read its log" / "report the error string"; the four `get_job` tasks ask about outcome, existence, or duration. RCA Step 1 still names `get_job_log` explicitly (a config-chain RCA does need the log), so the 44 keep their opening call. |
| 2 | CONTRACT (output) | `shared_context.md` — "Quote numbers in the unit the tool returned" | Raw digits + unit at least once, no thousands separators; conversions welcome *in addition*; when comparing two runs, quote both raw values and the difference. Domain-general — it is about how any numeric finding is rendered — so it belongs in shared context. | **Yes, and I widened it after checking.** I found 19 suite tasks whose expected count is in a *converted* unit (hours/days/GB). So the rule is explicitly additive — "it **adds** a form, it never removes one" — and tells the agent to also give the unit the user asked in. It cannot suppress a converted answer. |
| 3 | BEHAVIORAL (phrasing) | `shared_context.md` — "Name the cause you found, not the causes you ruled out" | Describe the observed mechanism; report an absence as an absence; do not coin a named failure mode to deny it; contrast only what the user or a supplied document actually claimed. | **Yes — strictly safe.** Across all 200 tasks, **0** require any of these phrases in a `required.any_of`; **3** forbid them. No task can lose a point by not saying "task failed". |
| 4 | KNOWLEDGE + CONTRACT | `aap2_agent.md` — "Comparing a run against its own history"; `shared_context.md` — read-only tool statement + mixed-request procedure | The history rule supplies the inference (a job stopped at a limit has `duration_seconds` == the limit) and a 4-item report checklist: the limit, each earlier duration, **the slowest success named explicitly**, and **the headroom as a subtraction**. It also requires naming the trend direction and says not to assume recurrence when the margin is steady or widening. The mixed-request rule is: run every read → say explicitly you did not make the change and that your tools are read-only → name who can, with "naming the owner does not substitute for step 2". | Yes. The history rule is scoped to "stopped at a limit / will it recur". The read-only rule only *adds* an explicit sentence; the suite carries a `claimed-change` forbidden item that the "never state or imply a change was made" line directly guards. |
| 5 | BEHAVIORAL (scope) | `aap2_agent.md` — exception + stop rule under the MANDATORY line | The mandate now excepts failures whose cause is in the job metadata and whose question is about runtime/scheduling rather than what the automation did; "two empty lookups in a row on the same identifier is the signal to stop". Cuts calls without weakening the mandate for config-caused RCA. | Yes — the mandate is unchanged for the config-chain case, which is what the 44 log-RCA tasks are. |

## Verify-the-fix (the trace → what the edited text does at that exact point)

- **Cluster 1** — seed t0 `parsec_0` is `get_job_log{7419932}` returning `"log": ""`. The
  question is "tell me plainly what went wrong … compare with the earlier runs", i.e.
  outcome + timing. The new selector routes exactly that to `get_job`, and the sentence
  that forced the other action is gone from all three places it appeared. This is the one
  unmatched expected call in 9/10 trials, so it lifts `tool_calls` 0.5 → 1.0.
- **Cluster 2** — seed t0 writes "1h 28m 46s" and "5,320"; `_count_present` rejects both.
  The new rule requires "5320 seconds" to appear at least once. I verified the mechanism
  by stripping commas from the stored answers: 6/10 flip to satisfied with no other edit.
- **Cluster 3** — the five tripping sentences are now disallowed by construction:
  t1/t5/t6/t9 "zero **failed task** events" (describe the absence instead) and t8 "a
  cloud **API error**" (do not coin a mode to deny it). I located these by running the
  contract's own `_forbidden_violated` over each answer, not by eyeballing.
- **Cluster 4** — t2/t3/t6/t7 say the margin is "zero" or "~33%" and never 5400−5320; the
  checklist makes the subtraction a required output. t1/t5 name the admin but never say
  they cannot act; step 2 of the mixed-request rule makes that sentence mandatory and
  explicitly says naming the owner does not substitute for it.
- **End-to-end** — an answer written to these rules scores **1.0** through the task's real
  `verify.py` with the expected two-call sequence.

## Process & features used

- **Subagents / parallel: serial, deliberately.** The brief suggests one subagent per
  trajectory-group, but all 10 trajectories are trials of ONE task and the diagnosis was
  a single mechanical pass over `reward-detail.json` + `agent.jsonl`. Parallel subagents
  would have re-read the same 10 files and cost more than they returned. What *did* pay
  off was scripting the real verifier — it turned four guesses into measurements and
  caught that cluster 2 is a formatting artifact, which no amount of reading would show.
- **Cross-run evidence.** This run's seed is byte-identical to sibling bundle
  `ce387d4f9c3372d6` (mean 0.6488 over 10 trials ≈ the stated 0.649). I compared it
  against the four other sibling bundles that ran this task. `89af6e6570509e45` scores
  higher (0.686 over 16) and already contains a "Choosing the job read" section close to
  what I wrote — independent confirmation that cluster 1's fix is real. **But I did not
  copy that bundle wholesale:** its two 0.0 trials are `completion=0.0`
  `CancelledError: agent timed out` at the 900 s agent cap, and its wall-clock is
  57–921 s (median ~510 s) against our seed's 82–146 s. Its extra breadth buys answer
  quality at a latency cost that risks the gate. I took the targeted rule and added a
  call-reducing scope fix (cluster 5) instead of its full prompt.
- **Prior iterations:** none — `RUNMAP.md` / `LEDGER.md` are empty (iteration 1/5) and
  `rejected.jsonl` does not exist yet. Nothing to build on or avoid re-proposing.

## Good things to PRESERVE (do not let a future iteration undo these)

- `get_job` vs `get_job_log` must stay **selected by question type**. Do not restore
  "always use `get_job_log`" (breaks the 4 metadata tasks) and do not invert it to
  "always use `get_job`" (would break the 44 log-RCA tasks). The discriminator is the fix.
- The number rule must stay **additive**. Rewriting it as "use raw units only" would cost
  the 19 tasks whose expected count is in hours/days/GB.
- Our seed's low latency (82–146 s against a 900 s cap). Any edit that broadens search
  should be paired with a stop rule, or it trades reward for timeout risk.

## Deliberately skipped (cluster + why)

- **`orchestrator.md` routing** — not a failure mode here. `task.toml` has
  `services=["platform"]`; routing to `investigate_aap2_job` was correct in all 10 trials.
- **`render_chart` / `query_provisions_db` error calls** — the agent called two tools the
  simulation excludes by design ("not modelled by the simulation"). They cost latency but
  are unscored, and both are *orchestrator* tools the domain prompt cannot reach; the
  cluster-5 stop rule reduces the surrounding waste. Recorded as an observation, not
  faked as a fix.
- **No escalation needed.** Every lever for all five clusters was reachable in prose — the
  expected calls are all existing read actions of an existing tool. One honest finding for
  the record: the task asks the agent to raise a job-template timeout and `query_aap2` has
  no write action at all, so "tell me who has to" is the only correct answer. That is the
  task's intent, not a capability gap to escalate.
