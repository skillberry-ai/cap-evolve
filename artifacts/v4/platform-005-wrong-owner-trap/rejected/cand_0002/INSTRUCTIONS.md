# Optimizing parsec v4's system prompts for one task

## THE READER (who consumes what you edit)
At runtime these capabilities are read by `claude-sonnet-4-6` — capability tier: **strong**. The reader is a capable general model, but less robust than frontier on long or ambiguous context. Keep instructions clear and reasonably explicit; add a worked example for tricky formats; prefer code enforcement for behavioral rules over trusting inference.
Optimize your edits for THIS reader's capability level, not for your own. When the reader is weaker than you, prefer explicit rules, worked examples, and code enforcement over terse prose you would personally infer.


Focus: every failing task on the val split. Current val reward 0.608: 0 solid / 1 flaky / 0 failing of 1 tasks.



## What you can edit

The capability is **`system-prompt`** — plain-text edits to the 8 files under
this project's candidate directory:

- `orchestrator.md` — routes every request to one of 6 domain agents below.
- `shared_context.md` — prepended to every domain agent's prompt (not the
  orchestrator's).
- `aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
  `ocpv_agent.md`, `security_agent.md` — one per domain.

There is **no tools/code layer** in this phase — you cannot add, remove, or
edit any Python tool. Every lever available to you is a change to what these
files *say*. If a failure looks like it needs a new tool or a code-level
guard, the honest fix within this phase's scope is a prose rule that gets the
agent to use its *existing* tools correctly (a missing capability that
genuinely requires new code is a real finding — write it into your
handover notes as an escalation, not something to fake with prose).

## The task you're optimizing for

This project's `train`, `val`, and `test` splits are all the *same single
task* (see `split_ids.json`) — there is no cross-task generalization question
this round. Every rollout you see is a different trial of that one task.
Your only question: **what does this one task's transcript show the agent
getting wrong, and which of the 8 files is the right place to fix it?**

Cross-reference the task's `task.toml` `services=[...]` against
`orchestrator.md`'s own routing text to find your task's actual prompt
footprint — almost always `orchestrator.md` + `shared_context.md` + one
domain file, occasionally two for cross-domain tasks.

## Choose the lever by failure type

- **Missing knowledge** (the agent didn't know a fact/convention it needed) →
  add a concrete prose rule to the file that should have carried it. Prefer
  the most specific file that's actually read for this task's domain over
  `shared_context.md` — only put a rule in `shared_context.md` if it is
  genuinely domain-general.
- **Wrong routing** (orchestrator sent the request to the wrong domain agent,
  or didn't route a cross-domain request to both) → tighten
  `orchestrator.md`'s routing rule with a *discriminating* condition (what
  distinguishes this case from the ones already routed correctly) — never
  a blanket "always route X to Y" that would misroute a case you haven't
  seen.
- **Right domain, wrong action** (agent reached the right sub-agent but chose
  the wrong tool call, wrong parameters, or stopped too early) → add a
  worked example or an explicit decision rule to that domain agent's file,
  anchored to the specific ambiguity that tripped it up.
- **Overcautious or overconfident** (agent asked for confirmation it didn't
  need, or asserted something it hadn't verified) → narrow the relevant
  rule with an explicit condition for *when* caution/confidence is
  warranted — never loosen a rule globally to fix one instance.

## Non-overfitting (read this before every edit)

Never hardcode this task's specific GUID, hostname, ticket number, or any
other instance-specific value into a prompt file. A rule that only works
because it names *this exact case* is not a fix — score gains for the
wrong reason don't survive a re-run with a different seed, let alone a
different task. Every rule you add must describe a *pattern* the next
similar case would also match.

## Verify the fix

Before finalizing a candidate: re-read the specific rollout(s) that failed
and check your edited text actually would have changed the agent's behavior
at the exact point it went wrong — not just that it's *plausible* it might
help. If it wouldn't have changed anything at that point, it isn't a fix,
even if it reads like good advice.

## Handover

At the end of your work on this candidate, write:

- `PROCESS.md` — what you tried, in the order you tried it, and why. A
  future reader (human or another optimizer run) should be able to follow
  your reasoning without re-deriving it from the diff alone.
- `JOURNAL.md` — append-only. One entry per iteration: what changed, what
  you expected it to fix, whether it did. Never rewrite a past entry —
  append a correction instead if you were wrong.

## Context for this run



Your agent supports parallel subagents/worktrees (see ./guidance/optimizer/claude-code.md). FAN OUT to cover MANY clusters at once: one read-only subagent per trajectory-group to diagnose, then one edit-subagent per issue (each in its own worktree), then MERGE every edit into this ONE candidate with no conflicts. This is how a single iteration fixes many issues across many trajectories, not just the biggest one.

---

## (b) 1 FLAKY task(s) — pass sometimes; make the good behavior consistent (full traces in ./trajectories/):
(reward is the mean over trials — the honest signal; the feedback line is from the LAST trial and may say 'passed' even when the mean is below 1.)
- platform-005-wrong-owner-trap (reward 0.61): Task fully solved (reward 1.0). Metrics: completion=1.0, tool_calls=1.0, answer=1.0.


## What you are editing (the allowed edit space)
The capability under optimization is composed of these editable artifact(s). Use the FULL edit space below — do not limit yourself to trivial wording tweaks.
- **system-prompt** — Optimize an agent's system prompt / policy text (instructions, output contract, decision policy).
  - Allowed edits: Edit the prompt/policy text: instructions, decision policy, and the output contract. Prefer sharpening rules the traces show the agent breaking; do not just append more preamble.
  - Full guidance (read it): ./guidance/system-prompt/SKILL.md
## How your edit is judged
Algorithm: hill-climb:all. Your edited candidate is re-scored on the SAME held-out val tasks and compared to the current best (val reward 0.608). It is ACCEPTED only if the per-task improvement clears a significance bar (a noise margin), so a tiny or lucky change is rejected. Aim for a real, generalizing gain across a CLASS of failures — not a one-off patch to a single task (that overfits and gets rejected or hurts the held-out test).


## Run budget (iteration 2/3 (1 after this one); $9.47/$50.00 spent (19%); 0/2 consecutive rejects)

## Cross-iteration files in THIS working dir (clean ownership — read all)
- `LEDGER.md` — FACTS (framework, read-only): every iteration's outcome + the tasks it MEASURABLY broke/fixed, plus the ones whose move was under 2·SE and so resolves nothing. Never re-introduce a change that broke a task; never redesign an edit because a task landed in `unresolved`.
- `JOURNAL.md` — HANDOVER (yours, append-only across the whole run): read the whole thing, then APPEND your entry for this iteration below the marker line. Do NOT edit earlier entries. This is how you avoid repeating refuted ideas and hitting the same plateau.
- `PROCESS.md` — EXPLAINABILITY (yours, REQUIRED this iteration): fill it in as you work (ranked issues, every edit + class, verify-the-fix, subagents/features used, what to preserve, what you skipped). It is snapshotted with your candidate.
- `RUNMAP.md` + `./prior_iterations/<id>/` — every prior iteration's PROCESS.md + capability diff, copied in for you. Read the ones targeting your cluster BEFORE proposing, so you build on prior work instead of repeating it.
- `INSIGHTS.md` — SUMMARIZED, VERIFIED findings (yours, append-only, optional most iterations): a distilled 'what worked / what didn't / what's promising' a future iteration reads INSTEAD of the whole journal. Add an entry whenever you have a new CONFIRMED finding (cite the RESULT that confirmed it).
- `META_INSIGHTS.md` — about the SEARCH PROCESS itself (yours, append-only): which strategies helped or stalled, what to try next. Update AT LEAST once, at the end of the run.
- `FRAMEWORK_IMPROVEMENTS.md` — cross-run suggestions for cap-evolve ITSELF, not this task (yours, append-only, optional): what confused you or was missing about the framework. Update AT LEAST once, at the end of the run.
- `v4_t2_e1_platform-005-wrong-owner-trap/run_20260920_103719/rejected.jsonl` — ALREADY-REFUTED approaches (framework, read-only; JSON lines, one per rejected candidate with the gate's reason). Read it and make each proposal STRUCTURALLY different from what is in it. Its sibling `history.jsonl` is the same record for accepts.

